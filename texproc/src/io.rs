use std::{
    fs::File,
    io::{BufReader, BufWriter, Cursor, Read, Seek, SeekFrom},
    path::Path,
};

use image::{DynamicImage, ImageFormat, ImageReader};
use tiff::encoder::{colortype, Compression, TiffEncoder};

use crate::{
    error::{Result, TexprocError},
    planar::PlanarImage,
};

const PNG_SIGNATURE: [u8; 8] = [137, 80, 78, 71, 13, 10, 26, 10];
const EXR_MAGIC: u32 = 20_000_630;
const MAX_HEADER_ITEM_BYTES: usize = 16 * 1024 * 1024;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct HeaderInfo {
    pub channels: u8,
    pub bit_depth: u8,
    pub width: u32,
    pub height: u32,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum SupportedFormat {
    Png,
    Jpeg,
    Tiff,
    Exr,
    Tga,
    Bmp,
    WebP,
}

fn extension_hint(path: &Path) -> Option<String> {
    path.extension()
        .and_then(|value| value.to_str())
        .map(|value| value.to_ascii_lowercase())
}

pub fn probe_header(path: impl AsRef<Path>) -> Result<HeaderInfo> {
    let path = path.as_ref();
    let file = File::open(path).map_err(|error| {
        TexprocError::new(format!("failed to open image header {}: {error}", path.display()))
    })?;
    let (header, _) = probe_reader(BufReader::new(file), extension_hint(path).as_deref())?;
    Ok(header)
}

pub fn decode_image(path: impl AsRef<Path>) -> Result<PlanarImage> {
    let path = path.as_ref();
    let file = File::open(path).map_err(|error| {
        TexprocError::new(format!("failed to open image {}: {error}", path.display()))
    })?;
    let (_, format) = probe_reader(BufReader::new(file), extension_hint(path).as_deref())?;
    let image_format = match format {
        SupportedFormat::Png => ImageFormat::Png,
        SupportedFormat::Jpeg => ImageFormat::Jpeg,
        SupportedFormat::Tiff => ImageFormat::Tiff,
        SupportedFormat::Exr => ImageFormat::OpenExr,
        SupportedFormat::Tga => ImageFormat::Tga,
        SupportedFormat::Bmp => ImageFormat::Bmp,
        SupportedFormat::WebP => ImageFormat::WebP,
    };

    let reader = ImageReader::with_format(BufReader::new(File::open(path)?), image_format);
    dynamic_to_planar(reader.decode()?)
}

pub fn write_tiff_lzw(path: impl AsRef<Path>, image: &PlanarImage) -> Result<()> {
    if !matches!(image.channels(), 1 | 3 | 4) {
        return Err(TexprocError::new(format!(
            "TIFF output supports gray, RGB, or RGBA, got {} channels",
            image.channels()
        )));
    }

    let writer = BufWriter::new(File::create(path.as_ref()).map_err(|error| {
        TexprocError::new(format!(
            "failed to create TIFF {}: {error}",
            path.as_ref().display()
        ))
    })?);
    let mut encoder = TiffEncoder::new(writer)?.with_compression(Compression::Lzw);
    let interleaved = image.to_interleaved_u8();
    match image.channels() {
        1 => encoder.write_image::<colortype::Gray8>(image.width, image.height, &interleaved)?,
        3 => encoder.write_image::<colortype::RGB8>(image.width, image.height, &interleaved)?,
        4 => encoder.write_image::<colortype::RGBA8>(image.width, image.height, &interleaved)?,
        _ => unreachable!("channel count was checked above"),
    }
    Ok(())
}

fn dynamic_to_planar(image: DynamicImage) -> Result<PlanarImage> {
    match image {
        DynamicImage::ImageLuma8(image) => {
            PlanarImage::from_interleaved_u8(image.width(), image.height(), 1, &image.into_raw())
        }
        DynamicImage::ImageLumaA8(image) => {
            PlanarImage::from_interleaved_u8(image.width(), image.height(), 2, &image.into_raw())
        }
        DynamicImage::ImageRgb8(image) => {
            PlanarImage::from_interleaved_u8(image.width(), image.height(), 3, &image.into_raw())
        }
        DynamicImage::ImageRgba8(image) => {
            PlanarImage::from_interleaved_u8(image.width(), image.height(), 4, &image.into_raw())
        }
        DynamicImage::ImageLuma16(image) => {
            PlanarImage::from_interleaved_u16(image.width(), image.height(), 1, &image.into_raw())
        }
        DynamicImage::ImageLumaA16(image) => {
            PlanarImage::from_interleaved_u16(image.width(), image.height(), 2, &image.into_raw())
        }
        DynamicImage::ImageRgb16(image) => {
            PlanarImage::from_interleaved_u16(image.width(), image.height(), 3, &image.into_raw())
        }
        DynamicImage::ImageRgba16(image) => {
            PlanarImage::from_interleaved_u16(image.width(), image.height(), 4, &image.into_raw())
        }
        DynamicImage::ImageRgb32F(image) => {
            PlanarImage::from_interleaved_f32(image.width(), image.height(), 3, &image.into_raw())
        }
        DynamicImage::ImageRgba32F(image) => {
            PlanarImage::from_interleaved_f32(image.width(), image.height(), 4, &image.into_raw())
        }
        other => Err(TexprocError::new(format!(
            "decoded color type {:?} is outside the T1 contract",
            other.color()
        ))),
    }
}

fn probe_reader<R: Read + Seek>(
    mut reader: R,
    ext_hint: Option<&str>,
) -> Result<(HeaderInfo, SupportedFormat)> {
    // 12 bytes covers every magic we sniff (WebP needs `RIFF....WEBP`); all
    // magic-bearing formats we accept have headers longer than this.
    let mut magic = [0_u8; 12];
    reader.read_exact(&mut magic)?;
    reader.seek(SeekFrom::Start(0))?;

    if magic[..8] == PNG_SIGNATURE {
        return Ok((probe_png(&mut reader)?, SupportedFormat::Png));
    }
    if magic[..2] == [0xff, 0xd8] {
        return Ok((probe_jpeg(&mut reader)?, SupportedFormat::Jpeg));
    }
    if matches!(&magic[..4], b"II*\0" | b"MM\0*") {
        return Ok((probe_tiff(&mut reader)?, SupportedFormat::Tiff));
    }
    if u32::from_le_bytes(magic[..4].try_into().expect("four-byte slice")) == EXR_MAGIC {
        return Ok((probe_exr(&mut reader)?, SupportedFormat::Exr));
    }
    if &magic[..2] == b"BM" {
        return Ok((probe_bmp(&mut reader)?, SupportedFormat::Bmp));
    }
    if &magic[..4] == b"RIFF" && &magic[8..12] == b"WEBP" {
        return Ok((probe_webp(&mut reader)?, SupportedFormat::WebP));
    }
    // TGA carries no leading magic (its signature is an optional footer), so it
    // is dispatched by file extension when no magic matched.
    if ext_hint.is_some_and(|ext| ext.eq_ignore_ascii_case("tga")) {
        return Ok((probe_tga(&mut reader)?, SupportedFormat::Tga));
    }

    Err(TexprocError::new(
        "unsupported image format; expected PNG, JPEG, TIFF, OpenEXR, TGA, BMP, or WebP",
    ))
}

/// TGA fixed 18-byte header: width/height are LE u16 at offsets 12/14 and the
/// pixel depth (total bits per pixel) is at offset 16. Channels are derived from
/// the depth; bit depth per channel is 8.
fn probe_tga<R: Read>(reader: &mut R) -> Result<HeaderInfo> {
    let mut header = [0_u8; 18];
    reader.read_exact(&mut header)?;
    let width = u32::from(u16::from_le_bytes([header[12], header[13]]));
    let height = u32::from(u16::from_le_bytes([header[14], header[15]]));
    let channels = match header[16] {
        8 => 1,
        16 => 2,
        24 => 3,
        32 => 4,
        depth => {
            return Err(TexprocError::new(format!(
                "unsupported TGA pixel depth {depth}"
            )))
        }
    };
    validate_header(channels, 8, width, height)
}

/// BMP: 14-byte file header (`BM`) then the DIB header. `BITMAPCOREHEADER`
/// (size 12) stores u16 dimensions; `BITMAPINFOHEADER` and its V4/V5 supersets
/// store i32 dimensions at the same offsets. Channels come from the bit count
/// (32-bit carries alpha).
fn probe_bmp<R: Read>(reader: &mut R) -> Result<HeaderInfo> {
    let mut file_header = [0_u8; 14];
    reader.read_exact(&mut file_header)?;
    if &file_header[..2] != b"BM" {
        return Err(TexprocError::new("invalid BMP signature"));
    }
    let dib_size = read_u32(reader, Endian::Little)?;
    let (width, height, bit_count) = if dib_size == 12 {
        let width = u32::from(read_u16(reader, Endian::Little)?);
        let height = u32::from(read_u16(reader, Endian::Little)?);
        let _planes = read_u16(reader, Endian::Little)?;
        (width, height, read_u16(reader, Endian::Little)?)
    } else {
        let width = read_u32(reader, Endian::Little)? as i32;
        let height = read_u32(reader, Endian::Little)? as i32;
        let _planes = read_u16(reader, Endian::Little)?;
        (
            width.unsigned_abs(),
            height.unsigned_abs(),
            read_u16(reader, Endian::Little)?,
        )
    };
    let channels = if bit_count >= 32 { 4 } else { 3 };
    validate_header(channels, 8, width, height)
}

/// WebP: 12-byte RIFF container (`RIFF....WEBP`) then a single VP8/VP8L/VP8X
/// chunk whose header carries the canvas dimensions.
fn probe_webp<R: Read>(reader: &mut R) -> Result<HeaderInfo> {
    let mut riff = [0_u8; 12];
    reader.read_exact(&mut riff)?;
    if &riff[..4] != b"RIFF" || &riff[8..12] != b"WEBP" {
        return Err(TexprocError::new("invalid WebP RIFF/WEBP signature"));
    }
    let mut chunk = [0_u8; 8];
    reader.read_exact(&mut chunk)?; // fourcc(4) + chunk size(4)
    match &chunk[..4] {
        b"VP8 " => {
            // Lossy keyframe: 3-byte frame tag, 3-byte start code, then 14-bit
            // width and height (each with a 2-bit scale in the high bits).
            let mut payload = [0_u8; 10];
            reader.read_exact(&mut payload)?;
            if payload[3..6] != [0x9d, 0x01, 0x2a] {
                return Err(TexprocError::new("invalid VP8 start code"));
            }
            let width = u32::from(u16::from_le_bytes([payload[6], payload[7]]) & 0x3fff);
            let height = u32::from(u16::from_le_bytes([payload[8], payload[9]]) & 0x3fff);
            validate_header(3, 8, width, height)
        }
        b"VP8L" => {
            let mut payload = [0_u8; 5];
            reader.read_exact(&mut payload)?;
            if payload[0] != 0x2f {
                return Err(TexprocError::new("invalid VP8L signature"));
            }
            let bits = u32::from_le_bytes([payload[1], payload[2], payload[3], payload[4]]);
            let width = (bits & 0x3fff) + 1;
            let height = ((bits >> 14) & 0x3fff) + 1;
            let channels = if (bits >> 28) & 1 == 1 { 4 } else { 3 };
            validate_header(channels, 8, width, height)
        }
        b"VP8X" => {
            // Extended: 4 flag/reserved bytes then 3-byte canvas width-1 and
            // 3-byte canvas height-1 (all little-endian).
            let mut payload = [0_u8; 10];
            reader.read_exact(&mut payload)?;
            let width = (u32::from_le_bytes([payload[4], payload[5], payload[6], 0]) & 0x00ff_ffff) + 1;
            let height = (u32::from_le_bytes([payload[7], payload[8], payload[9], 0]) & 0x00ff_ffff) + 1;
            let channels = if payload[0] & 0x10 != 0 { 4 } else { 3 };
            validate_header(channels, 8, width, height)
        }
        other => Err(TexprocError::new(format!(
            "unsupported WebP chunk {:?}; expected VP8/VP8L/VP8X",
            String::from_utf8_lossy(other)
        ))),
    }
}

fn probe_png<R: Read>(reader: &mut R) -> Result<HeaderInfo> {
    let mut header = [0_u8; 29];
    reader.read_exact(&mut header)?;
    if header[..8] != PNG_SIGNATURE || &header[12..16] != b"IHDR" {
        return Err(TexprocError::new("invalid PNG signature or missing IHDR"));
    }
    if u32::from_be_bytes(header[8..12].try_into().expect("four-byte slice")) != 13 {
        return Err(TexprocError::new("invalid PNG IHDR length"));
    }

    let width = u32::from_be_bytes(header[16..20].try_into().expect("four-byte slice"));
    let height = u32::from_be_bytes(header[20..24].try_into().expect("four-byte slice"));
    let bit_depth = header[24];
    let channels = match header[25] {
        0 => 1,
        2 => 3,
        3 => 3,
        4 => 2,
        6 => 4,
        color_type => {
            return Err(TexprocError::new(format!(
                "unsupported PNG color type {color_type}"
            )))
        }
    };
    validate_header(channels, bit_depth, width, height)
}

fn probe_jpeg<R: Read + Seek>(reader: &mut R) -> Result<HeaderInfo> {
    let mut soi = [0_u8; 2];
    reader.read_exact(&mut soi)?;
    if soi != [0xff, 0xd8] {
        return Err(TexprocError::new("invalid JPEG SOI marker"));
    }

    loop {
        let mut marker_start = [0_u8; 1];
        reader.read_exact(&mut marker_start)?;
        while marker_start[0] != 0xff {
            reader.read_exact(&mut marker_start)?;
        }
        let marker = loop {
            reader.read_exact(&mut marker_start)?;
            if marker_start[0] != 0xff {
                break marker_start[0];
            }
        };

        if marker == 0xd9 || marker == 0xda {
            return Err(TexprocError::new(
                "JPEG has no SOF metadata before pixel data",
            ));
        }
        if marker == 0x00 || marker == 0x01 || (0xd0..=0xd8).contains(&marker) {
            continue;
        }

        let segment_length = read_u16_be(reader)?;
        if segment_length < 2 {
            return Err(TexprocError::new("invalid JPEG segment length"));
        }
        if is_jpeg_sof(marker) {
            if segment_length < 8 {
                return Err(TexprocError::new("JPEG SOF segment is too short"));
            }
            let mut metadata = [0_u8; 6];
            reader.read_exact(&mut metadata)?;
            let bit_depth = metadata[0];
            let height = u32::from(u16::from_be_bytes([metadata[1], metadata[2]]));
            let width = u32::from(u16::from_be_bytes([metadata[3], metadata[4]]));
            let channels = metadata[5];
            return validate_header(channels, bit_depth, width, height);
        }
        reader.seek(SeekFrom::Current(i64::from(segment_length - 2)))?;
    }
}

fn is_jpeg_sof(marker: u8) -> bool {
    matches!(
        marker,
        0xc0 | 0xc1 | 0xc2 | 0xc3 | 0xc5 | 0xc6 | 0xc7 | 0xc9 | 0xca | 0xcb | 0xcd | 0xce | 0xcf
    )
}

#[derive(Clone, Copy)]
enum Endian {
    Little,
    Big,
}

fn probe_tiff<R: Read + Seek>(reader: &mut R) -> Result<HeaderInfo> {
    let mut byte_order = [0_u8; 2];
    reader.read_exact(&mut byte_order)?;
    let endian = match &byte_order {
        b"II" => Endian::Little,
        b"MM" => Endian::Big,
        _ => return Err(TexprocError::new("invalid TIFF byte order")),
    };
    if read_u16(reader, endian)? != 42 {
        return Err(TexprocError::new(
            "unsupported TIFF header (BigTIFF is outside the T1 contract)",
        ));
    }
    let ifd_offset = u64::from(read_u32(reader, endian)?);
    reader.seek(SeekFrom::Start(ifd_offset))?;
    let entry_count = read_u16(reader, endian)?;
    if entry_count > 4096 {
        return Err(TexprocError::new("TIFF IFD contains too many entries"));
    }

    let mut width = None;
    let mut height = None;
    let mut bit_depth = None;
    let mut channels = 1_u8;
    for _ in 0..entry_count {
        let tag = read_u16(reader, endian)?;
        let field_type = read_u16(reader, endian)?;
        let count = read_u32(reader, endian)?;
        let mut value_field = [0_u8; 4];
        reader.read_exact(&mut value_field)?;

        if matches!(tag, 256 | 257 | 258 | 277) {
            let values = read_tiff_values(reader, endian, field_type, count, value_field)?;
            match tag {
                256 => width = values.first().copied(),
                257 => height = values.first().copied(),
                258 => {
                    bit_depth = values
                        .into_iter()
                        .max()
                        .and_then(|value| u8::try_from(value).ok())
                }
                277 => {
                    channels = values
                        .first()
                        .copied()
                        .and_then(|value| u8::try_from(value).ok())
                        .ok_or_else(|| TexprocError::new("invalid TIFF SamplesPerPixel"))?;
                }
                _ => unreachable!(),
            }
        }
    }

    validate_header(
        channels,
        bit_depth.ok_or_else(|| TexprocError::new("TIFF BitsPerSample tag is missing"))?,
        width.ok_or_else(|| TexprocError::new("TIFF ImageWidth tag is missing"))?,
        height.ok_or_else(|| TexprocError::new("TIFF ImageLength tag is missing"))?,
    )
}

fn read_tiff_values<R: Read + Seek>(
    reader: &mut R,
    endian: Endian,
    field_type: u16,
    count: u32,
    value_field: [u8; 4],
) -> Result<Vec<u32>> {
    if count == 0 || count > 1024 {
        return Err(TexprocError::new("invalid TIFF metadata value count"));
    }
    let element_size = match field_type {
        3 => 2_usize,
        4 => 4_usize,
        _ => {
            return Err(TexprocError::new(format!(
                "unsupported TIFF metadata field type {field_type}"
            )))
        }
    };
    let byte_count = usize::try_from(count)
        .ok()
        .and_then(|value| value.checked_mul(element_size))
        .ok_or_else(|| TexprocError::new("TIFF metadata size overflow"))?;
    let mut bytes = vec![0_u8; byte_count];
    if byte_count <= value_field.len() {
        bytes.copy_from_slice(&value_field[..byte_count]);
    } else {
        let return_position = reader.stream_position()?;
        let offset = match endian {
            Endian::Little => u32::from_le_bytes(value_field),
            Endian::Big => u32::from_be_bytes(value_field),
        };
        reader.seek(SeekFrom::Start(u64::from(offset)))?;
        reader.read_exact(&mut bytes)?;
        reader.seek(SeekFrom::Start(return_position))?;
    }

    Ok(bytes
        .chunks_exact(element_size)
        .map(|chunk| match (field_type, endian) {
            (3, Endian::Little) => u32::from(u16::from_le_bytes([chunk[0], chunk[1]])),
            (3, Endian::Big) => u32::from(u16::from_be_bytes([chunk[0], chunk[1]])),
            (4, Endian::Little) => u32::from_le_bytes([chunk[0], chunk[1], chunk[2], chunk[3]]),
            (4, Endian::Big) => u32::from_be_bytes([chunk[0], chunk[1], chunk[2], chunk[3]]),
            _ => unreachable!("field type was validated"),
        })
        .collect())
}

fn probe_exr<R: Read>(reader: &mut R) -> Result<HeaderInfo> {
    if read_u32_le(reader)? != EXR_MAGIC {
        return Err(TexprocError::new("invalid OpenEXR magic"));
    }
    let _version = read_u32_le(reader)?;
    let mut channels = None;
    let mut bit_depth = None;
    let mut dimensions = None;

    for _ in 0..1024 {
        let name = read_c_string(reader, 255)?;
        if name.is_empty() {
            break;
        }
        let attribute_type = read_c_string(reader, 255)?;
        let byte_count = usize::try_from(read_u32_le(reader)?)
            .map_err(|_| TexprocError::new("OpenEXR attribute size overflow"))?;
        if byte_count > MAX_HEADER_ITEM_BYTES {
            return Err(TexprocError::new("OpenEXR attribute is unreasonably large"));
        }
        let mut payload = vec![0_u8; byte_count];
        reader.read_exact(&mut payload)?;

        if name == "channels" && attribute_type == "chlist" {
            let (count, depth) = parse_exr_channels(&payload)?;
            channels = Some(count);
            bit_depth = Some(depth);
        } else if name == "dataWindow" && attribute_type == "box2i" {
            dimensions = Some(parse_exr_data_window(&payload)?);
        }
    }

    let (width, height) =
        dimensions.ok_or_else(|| TexprocError::new("OpenEXR dataWindow is missing"))?;
    validate_header(
        channels.ok_or_else(|| TexprocError::new("OpenEXR channel list is missing"))?,
        bit_depth.ok_or_else(|| TexprocError::new("OpenEXR channel depth is missing"))?,
        width,
        height,
    )
}

fn parse_exr_channels(payload: &[u8]) -> Result<(u8, u8)> {
    let mut cursor = Cursor::new(payload);
    let mut channel_count = 0_u8;
    let mut bit_depth = 0_u8;
    while usize::try_from(cursor.position()).unwrap_or(usize::MAX) < payload.len() {
        let name = read_c_string(&mut cursor, 255)?;
        if name.is_empty() {
            break;
        }
        let pixel_type = read_u32_le(&mut cursor)?;
        let depth = match pixel_type {
            0 | 2 => 32,
            1 => 16,
            _ => {
                return Err(TexprocError::new(format!(
                    "unsupported OpenEXR pixel type {pixel_type}"
                )))
            }
        };
        let mut sampling = [0_u8; 12];
        cursor.read_exact(&mut sampling)?;
        channel_count = channel_count
            .checked_add(1)
            .ok_or_else(|| TexprocError::new("too many OpenEXR channels"))?;
        bit_depth = bit_depth.max(depth);
    }
    if channel_count == 0 {
        return Err(TexprocError::new("OpenEXR channel list is empty"));
    }
    Ok((channel_count, bit_depth))
}

fn parse_exr_data_window(payload: &[u8]) -> Result<(u32, u32)> {
    if payload.len() != 16 {
        return Err(TexprocError::new("invalid OpenEXR dataWindow size"));
    }
    let minimum_x = i32::from_le_bytes(payload[0..4].try_into().expect("four-byte slice"));
    let minimum_y = i32::from_le_bytes(payload[4..8].try_into().expect("four-byte slice"));
    let maximum_x = i32::from_le_bytes(payload[8..12].try_into().expect("four-byte slice"));
    let maximum_y = i32::from_le_bytes(payload[12..16].try_into().expect("four-byte slice"));
    let width = i64::from(maximum_x) - i64::from(minimum_x) + 1;
    let height = i64::from(maximum_y) - i64::from(minimum_y) + 1;
    if width <= 0 || height <= 0 {
        return Err(TexprocError::new("invalid OpenEXR dataWindow bounds"));
    }
    Ok((
        u32::try_from(width).map_err(|_| TexprocError::new("OpenEXR width overflow"))?,
        u32::try_from(height).map_err(|_| TexprocError::new("OpenEXR height overflow"))?,
    ))
}

fn validate_header(channels: u8, bit_depth: u8, width: u32, height: u32) -> Result<HeaderInfo> {
    if channels == 0 || bit_depth == 0 || width == 0 || height == 0 {
        return Err(TexprocError::new(format!(
            "invalid image metadata: channels={channels}, depth={bit_depth}, size={width}x{height}"
        )));
    }
    Ok(HeaderInfo {
        channels,
        bit_depth,
        width,
        height,
    })
}

fn read_c_string(reader: &mut impl Read, maximum_length: usize) -> Result<String> {
    let mut bytes = Vec::new();
    loop {
        let mut byte = [0_u8; 1];
        reader.read_exact(&mut byte)?;
        if byte[0] == 0 {
            break;
        }
        if bytes.len() == maximum_length {
            return Err(TexprocError::new("header string exceeds its size limit"));
        }
        bytes.push(byte[0]);
    }
    String::from_utf8(bytes).map_err(|_| TexprocError::new("header contains invalid UTF-8"))
}

fn read_u16_be(reader: &mut impl Read) -> Result<u16> {
    let mut bytes = [0_u8; 2];
    reader.read_exact(&mut bytes)?;
    Ok(u16::from_be_bytes(bytes))
}

fn read_u16(reader: &mut impl Read, endian: Endian) -> Result<u16> {
    let mut bytes = [0_u8; 2];
    reader.read_exact(&mut bytes)?;
    Ok(match endian {
        Endian::Little => u16::from_le_bytes(bytes),
        Endian::Big => u16::from_be_bytes(bytes),
    })
}

fn read_u32(reader: &mut impl Read, endian: Endian) -> Result<u32> {
    let mut bytes = [0_u8; 4];
    reader.read_exact(&mut bytes)?;
    Ok(match endian {
        Endian::Little => u32::from_le_bytes(bytes),
        Endian::Big => u32::from_be_bytes(bytes),
    })
}

fn read_u32_le(reader: &mut impl Read) -> Result<u32> {
    let mut bytes = [0_u8; 4];
    reader.read_exact(&mut bytes)?;
    Ok(u32::from_le_bytes(bytes))
}

#[cfg(test)]
mod tests {
    use std::{
        fs,
        io::BufWriter,
        sync::atomic::{AtomicU64, Ordering},
    };

    use image::{
        codecs::openexr::OpenExrEncoder, ColorType, ExtendedColorType, ImageEncoder, ImageFormat,
    };
    use tiff::{
        decoder::{Decoder, DecodingResult},
        encoder::{colortype, TiffEncoder},
        tags::Tag,
    };

    use super::*;

    static NEXT_TEST_FILE: AtomicU64 = AtomicU64::new(0);

    struct TestFile(std::path::PathBuf);

    impl TestFile {
        fn new(extension: &str) -> Self {
            let serial = NEXT_TEST_FILE.fetch_add(1, Ordering::Relaxed);
            Self(std::env::temp_dir().join(format!(
                "texproc-t009-{}-{serial}.{extension}",
                std::process::id()
            )))
        }
    }

    impl Drop for TestFile {
        fn drop(&mut self) {
            let _ = fs::remove_file(&self.0);
        }
    }

    fn write_header_probe(bytes: &[u8], extension: &str) -> TestFile {
        let file = TestFile::new(extension);
        fs::write(&file.0, bytes).unwrap();
        file
    }

    #[test]
    fn png_header_probe_needs_no_pixel_payload() {
        let mut bytes = PNG_SIGNATURE.to_vec();
        bytes.extend_from_slice(&13_u32.to_be_bytes());
        bytes.extend_from_slice(b"IHDR");
        bytes.extend_from_slice(&7_u32.to_be_bytes());
        bytes.extend_from_slice(&5_u32.to_be_bytes());
        bytes.extend_from_slice(&[16, 6, 0, 0, 0]);
        bytes.extend_from_slice(&[0; 4]);
        let file = write_header_probe(&bytes, "png");
        assert_eq!(
            probe_header(&file.0).unwrap(),
            HeaderInfo {
                channels: 4,
                bit_depth: 16,
                width: 7,
                height: 5
            }
        );
        assert!(decode_image(&file.0).is_err());
    }

    #[test]
    fn jpeg_header_probe_needs_no_pixel_payload() {
        let mut bytes = vec![0xff, 0xd8, 0xff, 0xc0];
        bytes.extend_from_slice(&17_u16.to_be_bytes());
        bytes.extend_from_slice(&[8]);
        bytes.extend_from_slice(&5_u16.to_be_bytes());
        bytes.extend_from_slice(&7_u16.to_be_bytes());
        bytes.push(3);
        bytes.extend_from_slice(&[1, 0x11, 0, 2, 0x11, 0, 3, 0x11, 0]);
        let file = write_header_probe(&bytes, "jpg");
        assert_eq!(
            probe_header(&file.0).unwrap(),
            HeaderInfo {
                channels: 3,
                bit_depth: 8,
                width: 7,
                height: 5
            }
        );
        assert!(decode_image(&file.0).is_err());
    }

    #[test]
    fn tiff_header_probe_needs_no_pixel_payload() {
        let mut bytes = b"II*\0".to_vec();
        bytes.extend_from_slice(&8_u32.to_le_bytes());
        bytes.extend_from_slice(&4_u16.to_le_bytes());
        push_tiff_entry(&mut bytes, 256, 4, 1, 7);
        push_tiff_entry(&mut bytes, 257, 4, 1, 5);
        push_tiff_entry(&mut bytes, 258, 3, 4, 62);
        push_tiff_entry(&mut bytes, 277, 3, 1, 4);
        bytes.extend_from_slice(&0_u32.to_le_bytes());
        for _ in 0..4 {
            bytes.extend_from_slice(&16_u16.to_le_bytes());
        }
        let file = write_header_probe(&bytes, "tif");
        assert_eq!(
            probe_header(&file.0).unwrap(),
            HeaderInfo {
                channels: 4,
                bit_depth: 16,
                width: 7,
                height: 5
            }
        );
        assert!(decode_image(&file.0).is_err());
    }

    #[test]
    fn exr_header_probe_needs_no_pixel_payload() {
        let bytes = minimal_exr_header(7, 5, &["R", "G", "B", "A"], 1);
        let file = write_header_probe(&bytes, "exr");
        assert_eq!(
            probe_header(&file.0).unwrap(),
            HeaderInfo {
                channels: 4,
                bit_depth: 16,
                width: 7,
                height: 5
            }
        );
        assert!(decode_image(&file.0).is_err());
    }

    #[test]
    fn decode_png_and_jpeg_u8_inputs() {
        let png = TestFile::new("png");
        image::save_buffer_with_format(
            &png.0,
            &[0, 128, 255, 255, 0, 64],
            2,
            1,
            ColorType::Rgb8,
            ImageFormat::Png,
        )
        .unwrap();
        let decoded_png = decode_image(&png.0).unwrap();
        assert_eq!(
            (
                decoded_png.width,
                decoded_png.height,
                decoded_png.channels()
            ),
            (2, 1, 3)
        );
        assert_eq!(
            decoded_png.to_interleaved_u8(),
            vec![0, 128, 255, 255, 0, 64]
        );

        let jpeg = TestFile::new("jpg");
        image::save_buffer_with_format(
            &jpeg.0,
            &[64, 64, 64],
            1,
            1,
            ColorType::Rgb8,
            ImageFormat::Jpeg,
        )
        .unwrap();
        let decoded_jpeg = decode_image(&jpeg.0).unwrap();
        assert_eq!(
            (
                decoded_jpeg.width,
                decoded_jpeg.height,
                decoded_jpeg.channels()
            ),
            (1, 1, 3)
        );
    }

    // --- T-016: TGA / BMP / WebP source formats ---------------------------

    /// Anchor 1: TGA (uncompressed + RLE) decodes pixel-identical to the same
    /// content saved as PNG. The image crate encodes TGA as RLE by default, so
    /// the uncompressed case is written with an explicit encoder option.
    #[test]
    fn decode_tga_rle_and_uncompressed_match_png() {
        use image::codecs::tga::TgaEncoder;
        use image::RgbImage;

        let pixels: Vec<u8> = vec![
            10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 200, 190, 180, 30, 30, 30,
        ];
        let rgb = RgbImage::from_raw(3, 2, pixels.clone()).unwrap();

        let png = TestFile::new("png");
        rgb.save_with_format(&png.0, ImageFormat::Png).unwrap();
        let expected = decode_image(&png.0).unwrap().to_interleaved_u8();

        // RLE (image crate default for TGA).
        let tga_rle = TestFile::new("tga");
        rgb.save_with_format(&tga_rle.0, ImageFormat::Tga).unwrap();
        assert_eq!(decode_image(&tga_rle.0).unwrap().to_interleaved_u8(), expected);

        // Uncompressed via the explicit encoder (RLE disabled).
        let tga_raw = TestFile::new("tga");
        {
            let mut writer = BufWriter::new(File::create(&tga_raw.0).unwrap());
            TgaEncoder::new(&mut writer)
                .disable_rle()
                .encode(&pixels, 3, 2, ExtendedColorType::Rgb8)
                .unwrap();
        }
        assert_eq!(decode_image(&tga_raw.0).unwrap().to_interleaved_u8(), expected);
    }

    /// Anchor 1: BMP decodes pixel-identical to the same content saved as PNG.
    #[test]
    fn decode_bmp_matches_png() {
        use image::RgbImage;

        let pixels: Vec<u8> = vec![
            10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 200, 190, 180, 30, 30, 30,
        ];
        let rgb = RgbImage::from_raw(3, 2, pixels).unwrap();

        let png = TestFile::new("png");
        rgb.save_with_format(&png.0, ImageFormat::Png).unwrap();
        let expected = decode_image(&png.0).unwrap().to_interleaved_u8();

        let bmp = TestFile::new("bmp");
        rgb.save_with_format(&bmp.0, ImageFormat::Bmp).unwrap();
        assert_eq!(decode_image(&bmp.0).unwrap().to_interleaved_u8(), expected);
    }

    /// Anchor 1: lossless WebP decodes pixel-identical to the same content saved
    /// as PNG; a lossy WebP is only proven to decode (no bit comparison).
    #[test]
    fn decode_webp_lossless_matches_png_and_lossy_decodes() {
        use image::codecs::webp::WebPEncoder;
        use image::RgbImage;

        let pixels: Vec<u8> = vec![
            10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 200, 190, 180, 30, 30, 30,
        ];
        let rgb = RgbImage::from_raw(3, 2, pixels.clone()).unwrap();

        let png = TestFile::new("png");
        rgb.save_with_format(&png.0, ImageFormat::Png).unwrap();
        let expected = decode_image(&png.0).unwrap();

        // Lossless (image-webp only encodes lossless).
        let webp = TestFile::new("webp");
        {
            let writer = BufWriter::new(File::create(&webp.0).unwrap());
            WebPEncoder::new_lossless(writer)
                .encode(&pixels, 3, 2, ExtendedColorType::Rgb8)
                .unwrap();
        }
        let decoded = decode_image(&webp.0).unwrap();
        assert_eq!(
            (decoded.width, decoded.height),
            (expected.width, expected.height)
        );
        // Compare the RGB planes regardless of a decoder-added opaque alpha.
        for channel in 0..3 {
            assert_eq!(decoded.planes[channel], expected.planes[channel]);
        }

        // Lossy: just prove it decodes into the T1 contract.
        let lossy = webp_lossy_fixture();
        let file = write_header_probe(&lossy, "webp");
        assert!(decode_image(&file.0).is_ok());
    }

    /// Anchor 2: probe_header reports correct w/h/channels for all three
    /// formats without decoding pixels.
    #[test]
    fn probe_header_reports_dimensions_for_new_formats() {
        use image::{RgbImage, RgbaImage};

        // TGA 24-bit -> 3 channels.
        let tga = TestFile::new("tga");
        RgbImage::from_raw(7, 5, vec![128; 7 * 5 * 3])
            .unwrap()
            .save_with_format(&tga.0, ImageFormat::Tga)
            .unwrap();
        assert_eq!(
            probe_header(&tga.0).unwrap(),
            HeaderInfo { channels: 3, bit_depth: 8, width: 7, height: 5 }
        );

        // BMP 32-bit RGBA -> 4 channels.
        let bmp = TestFile::new("bmp");
        RgbaImage::from_raw(7, 5, vec![64; 7 * 5 * 4])
            .unwrap()
            .save_with_format(&bmp.0, ImageFormat::Bmp)
            .unwrap();
        assert_eq!(
            probe_header(&bmp.0).unwrap(),
            HeaderInfo { channels: 4, bit_depth: 8, width: 7, height: 5 }
        );

        // WebP lossless from RGB -> 3 channels.
        let webp = TestFile::new("webp");
        {
            use image::codecs::webp::WebPEncoder;
            let writer = BufWriter::new(File::create(&webp.0).unwrap());
            WebPEncoder::new_lossless(writer)
                .encode(&vec![200; 7 * 5 * 3], 7, 5, ExtendedColorType::Rgb8)
                .unwrap();
        }
        assert_eq!(
            probe_header(&webp.0).unwrap(),
            HeaderInfo { channels: 3, bit_depth: 8, width: 7, height: 5 }
        );
    }

    /// image-webp only encodes lossless, so the lossy proof uses a real 4x4 VP8
    /// (lossy) file generated once with libwebp/ImageMagick.
    fn webp_lossy_fixture() -> Vec<u8> {
        const BYTES: &[u8] = &[
            0x52, 0x49, 0x46, 0x46, 0x34, 0x00, 0x00, 0x00, 0x57, 0x45, 0x42, 0x50, 0x56, 0x50,
            0x38, 0x20, 0x28, 0x00, 0x00, 0x00, 0x90, 0x01, 0x00, 0x9d, 0x01, 0x2a, 0x04, 0x00,
            0x04, 0x00, 0x02, 0x00, 0x34, 0x25, 0xa0, 0x02, 0x74, 0xba, 0x00, 0x03, 0x98, 0x00,
            0xfe, 0xd6, 0x31, 0xff, 0x70, 0x66, 0x7d, 0x5d, 0x8e, 0x1f, 0xdc, 0xd8, 0xe7, 0x16,
            0xc8, 0x60, 0x00, 0x00,
        ];
        BYTES.to_vec()
    }

    #[test]
    fn decode_16_bit_tiff_normalizes_to_unit_f32() {
        let file = TestFile::new("tif");
        let writer = BufWriter::new(File::create(&file.0).unwrap());
        TiffEncoder::new(writer)
            .unwrap()
            .write_image::<colortype::Gray16>(3, 1, &[0, 32_768, 65_535])
            .unwrap();

        let header = probe_header(&file.0).unwrap();
        assert_eq!(header.bit_depth, 16);
        let decoded = decode_image(&file.0).unwrap();
        assert_eq!(decoded.planes[0][0], 0.0);
        assert!((decoded.planes[0][1] - 32_768.0 / 65_535.0).abs() < 1.0e-6);
        assert_eq!(decoded.planes[0][2], 1.0);
    }

    #[test]
    fn decode_exr_preserves_f32_without_integer_quantization() {
        let file = TestFile::new("exr");
        let samples = [0.125_f32, 0.25, 0.5, 1.25, -0.5, 0.75];
        let bytes = samples
            .iter()
            .flat_map(|sample| sample.to_ne_bytes())
            .collect::<Vec<_>>();
        OpenExrEncoder::new(BufWriter::new(File::create(&file.0).unwrap()))
            .write_image(&bytes, 2, 1, ExtendedColorType::Rgb32F)
            .unwrap();

        let decoded = decode_image(&file.0).unwrap();
        assert_eq!(
            (decoded.width, decoded.height, decoded.channels()),
            (2, 1, 3)
        );
        assert_eq!(decoded.planes[0], vec![0.125, 1.0]);
        assert_eq!(decoded.planes[1], vec![0.25, 0.0]);
        assert_eq!(decoded.planes[2], vec![0.5, 0.75]);
    }

    #[test]
    fn tiff_output_is_8_bit_lzw_for_gray_rgb_and_rgba() {
        for channels in [1, 3, 4] {
            let file = TestFile::new("tif");
            let image = PlanarImage::new(
                1,
                1,
                (0..channels)
                    .map(|channel| vec![channel as f32 / channels as f32])
                    .collect(),
            )
            .unwrap();
            write_tiff_lzw(&file.0, &image).unwrap();

            let mut decoder = Decoder::new(BufReader::new(File::open(&file.0).unwrap())).unwrap();
            let compression: u16 = decoder.get_tag_unsigned(Tag::Compression).unwrap();
            assert_eq!(compression, 5);
            assert_eq!(decoder.dimensions().unwrap(), (1, 1));
            assert!(matches!(
                decoder.read_image().unwrap(),
                DecodingResult::U8(_)
            ));
        }
    }

    fn push_tiff_entry(output: &mut Vec<u8>, tag: u16, field_type: u16, count: u32, value: u32) {
        output.extend_from_slice(&tag.to_le_bytes());
        output.extend_from_slice(&field_type.to_le_bytes());
        output.extend_from_slice(&count.to_le_bytes());
        output.extend_from_slice(&value.to_le_bytes());
    }

    fn minimal_exr_header(
        width: u32,
        height: u32,
        channel_names: &[&str],
        pixel_type: u32,
    ) -> Vec<u8> {
        let mut output = EXR_MAGIC.to_le_bytes().to_vec();
        output.extend_from_slice(&2_u32.to_le_bytes());

        let mut channels = Vec::new();
        for name in channel_names {
            channels.extend_from_slice(name.as_bytes());
            channels.push(0);
            channels.extend_from_slice(&pixel_type.to_le_bytes());
            channels.extend_from_slice(&[0; 4]);
            channels.extend_from_slice(&1_i32.to_le_bytes());
            channels.extend_from_slice(&1_i32.to_le_bytes());
        }
        channels.push(0);
        push_exr_attribute(&mut output, "channels", "chlist", &channels);

        let mut data_window = Vec::new();
        data_window.extend_from_slice(&0_i32.to_le_bytes());
        data_window.extend_from_slice(&0_i32.to_le_bytes());
        data_window.extend_from_slice(&(width as i32 - 1).to_le_bytes());
        data_window.extend_from_slice(&(height as i32 - 1).to_le_bytes());
        push_exr_attribute(&mut output, "dataWindow", "box2i", &data_window);
        output.push(0);
        output
    }

    fn push_exr_attribute(output: &mut Vec<u8>, name: &str, kind: &str, payload: &[u8]) {
        output.extend_from_slice(name.as_bytes());
        output.push(0);
        output.extend_from_slice(kind.as_bytes());
        output.push(0);
        output.extend_from_slice(&(payload.len() as u32).to_le_bytes());
        output.extend_from_slice(payload);
    }
}
