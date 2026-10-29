//! Native flat EXR channel decoding shared by materials, previews and HDR staging.
//! Read the first flat part at its largest resolution. Prefer unprefixed RGB/Y,
//! then a complete named channel layer; never combine unrelated channel layers.
use std::path::Path;

use crate::{PlanarImage, Result, TexprocError};

pub(crate) struct ExrPixels {
    pub width: u32,
    pub height: u32,
    pub planes: Vec<Vec<f32>>,
}

pub(crate) fn select_channels(names: &[String]) -> Result<Vec<usize>> {
    let names: Vec<String> = names.iter().map(|name| name.to_ascii_lowercase()).collect();
    let mut prefixes = vec![String::new()];
    for name in &names {
        if let Some((prefix, _)) = name.rsplit_once('.') {
            let prefix = format!("{prefix}.");
            if !prefixes.contains(&prefix) {
                prefixes.push(prefix);
            }
        }
    }
    for prefix in prefixes {
        let find = |channel: &str| names.iter().position(|name| name == &format!("{prefix}{channel}"));
        let mut selected = if let (Some(r), Some(g), Some(b)) = (find("r"), find("g"), find("b")) {
            vec![r, g, b]
        } else if let Some(y) = find("y") {
            vec![y]
        } else {
            continue;
        };
        if let Some(alpha) = find("a") {
            selected.push(alpha);
        }
        return Ok(selected);
    }
    // Scalar maps may use R, Z, roughness, or any other single channel name.
    let scalar: Vec<usize> = names.iter().enumerate()
        .filter(|(_, name)| name.as_str() != "a").map(|(index, _)| index).collect();
    if scalar.len() == 1 {
        let mut selected = scalar;
        if let Some(alpha) = names.iter().position(|name| name == "a") {
            selected.push(alpha);
        }
        return Ok(selected);
    }
    if names.len() == 1 {
        return Ok(vec![0]);
    }
    Err(TexprocError::new(format!(
        "EXR has no unambiguous RGB, Y or scalar channel set: {}", names.join(", ")
    )))
}

pub(crate) fn read_pixels(path: &Path) -> Result<ExrPixels> {
    let image = exr::prelude::read_first_flat_layer_from_file(path)
        .map_err(|error| TexprocError::new(format!("EXR decode failed for {}: {error}", path.display())))?;
    let layer = image.layer_data;
    let channels = layer.channel_data.list;
    let names = channels.iter().map(|channel| channel.name.to_string()).collect::<Vec<_>>();
    let selection = select_channels(&names)?;
    let width = u32::try_from(layer.size.width()).map_err(|_| TexprocError::new("EXR width overflow"))?;
    let height = u32::try_from(layer.size.height()).map_err(|_| TexprocError::new("EXR height overflow"))?;
    let planes = selection.into_iter().map(|index| {
        let channel = &channels[index];
        if channel.sampling != exr::math::Vec2(1, 1) {
            return Err(TexprocError::new(format!("EXR channel {} uses unsupported subsampling", channel.name)));
        }
        let samples: Vec<f32> = channel.sample_data.values_as_f32().collect();
        if samples.len() != layer.size.area() || samples.iter().any(|sample| !sample.is_finite()) {
            return Err(TexprocError::new(format!("EXR channel {} has invalid or non-finite samples", channel.name)));
        }
        Ok(samples)
    }).collect::<Result<Vec<_>>>()?;
    Ok(ExrPixels { width, height, planes })
}

pub(crate) fn decode_material(path: &Path) -> Result<PlanarImage> {
    let mut pixels = read_pixels(path)?;
    // Material processing has an explicit normalized 0..1 contract. Environment
    // staging uses read_pixels directly to preserve HDR radiance above 1.
    for sample in pixels.planes.iter_mut().flatten() {
        *sample = sample.clamp(0.0, 1.0);
    }
    if pixels.planes.len() == 2 {
        let alpha = pixels.planes.pop().unwrap();
        pixels.planes.push(pixels.planes[0].clone());
        pixels.planes.push(pixels.planes[0].clone());
        pixels.planes.push(alpha);
    }
    PlanarImage::new(pixels.width, pixels.height, pixels.planes)
}

#[cfg(test)]
pub(crate) mod tests {
    use super::*;
    use exr::prelude::*;

    pub(crate) fn write_channels(path: &Path, channels: &[(&str, FlatSamples)], encoding: Encoding) {
        let layer = Layer::new((2, 2), LayerAttributes::default(), encoding,
            AnyChannels::sort(channels.iter().map(|(name, samples)| AnyChannel::new(*name, samples.clone())).collect()));
        Image::from_layer(layer).write().to_file(path).unwrap();
    }

    fn temp_dir() -> std::path::PathBuf {
        let dir = std::env::temp_dir().join(format!("texproc-native-exr-{}-{}", std::process::id(),
            std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_nanos()));
        std::fs::create_dir_all(&dir).unwrap();
        dir
    }

    #[test]
    fn scalar_half_float_uint_and_gray_alpha_decode_without_rgb_requirement() {
        let dir = temp_dir();
        for (name, samples, expected) in [
            ("Y", FlatSamples::F16(vec![f16::from_f32(0.375); 4]), 0.375),
            ("R", FlatSamples::F32(vec![0.123456; 4]), 0.123456),
            ("Z", FlatSamples::U32(vec![1; 4]), 1.0),
            ("roughness", FlatSamples::F32(vec![0.75; 4]), 0.75),
        ] {
            let path = dir.join(format!("{name}.exr"));
            write_channels(&path, &[(name, samples)], Encoding::default());
            assert_eq!(crate::probe_header(&path).unwrap().channels, 1);
            let decoded = crate::decode_image(&path).unwrap();
            assert_eq!(decoded.channels(), 1);
            assert_eq!(decoded.planes[0], vec![expected; 4]);
        }
        let path = dir.join("ya.exr");
        write_channels(&path, &[("Y", FlatSamples::F32(vec![0.3; 4])), ("A", FlatSamples::F32(vec![0.7; 4]))], Encoding::default());
        assert_eq!(crate::probe_header(&path).unwrap().channels, 2);
        let decoded = crate::decode_image(&path).unwrap();
        assert_eq!(decoded.channels(), 4);
        assert_eq!(decoded.planes[3], vec![0.7; 4]);
        std::fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn named_rgb_channels_ignore_auxiliary_channels_and_preserve_hdr_in_staging() {
        let dir = temp_dir();
        let path = dir.join("studio.exr");
        write_channels(&path, &[
            ("beauty.R", FlatSamples::F32(vec![4.0; 4])),
            ("beauty.G", FlatSamples::F32(vec![0.5; 4])),
            ("beauty.B", FlatSamples::F32(vec![0.25; 4])),
            ("beauty.A", FlatSamples::F32(vec![1.0; 4])),
            ("Z", FlatSamples::F32(vec![99.0; 4])),
        ], Encoding::default());
        assert_eq!(crate::probe_header(&path).unwrap().channels, 4);
        assert_eq!(read_pixels(&path).unwrap().planes[0], vec![4.0; 4]);
        assert_eq!(crate::decode_image(&path).unwrap().planes[0], vec![1.0; 4]);
        let staged = crate::stage_passthrough(&path, &dir).unwrap();
        let hdr = image::ImageReader::open(&staged).unwrap().decode().unwrap().to_rgb32f();
        assert_eq!(hdr.get_pixel(0, 0)[0], 4.0);
        assert!(crate::decode_image(&staged).is_ok(), "HDR preview must decode");
        std::fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn scanline_and_tiled_compression_matrix() {
        let dir = temp_dir();
        for compression in [Compression::Uncompressed, Compression::RLE, Compression::ZIP1,
            Compression::ZIP16, Compression::PIZ, Compression::PXR24, Compression::B44,
            Compression::B44A, Compression::DWAA(None), Compression::DWAB(None)] {
            for blocks in [Blocks::ScanLines, Blocks::Tiles(Vec2(2, 2))] {
                let path = dir.join("compression.exr");
                let samples = FlatSamples::F16(vec![f16::from_f32(0.375); 4]);
                write_channels(&path, &[("R", samples.clone()), ("G", samples.clone()), ("B", samples)],
                    Encoding { compression, blocks, line_order: LineOrder::Increasing });
                let decoded = crate::decode_image(&path).unwrap_or_else(|error| panic!("{compression:?} {blocks:?}: {error}"));
                assert!(decoded.planes.iter().flatten().all(|value| (value - 0.375).abs() < 0.03));
            }
        }
        std::fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn ambiguous_channels_are_reported_instead_of_guessed() {
        assert!(select_channels(&["foo".into(), "bar".into()]).is_err());
        assert!(select_channels(&["one.R".into(), "two.G".into(), "three.B".into()]).is_err());
    }
}
