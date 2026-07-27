//! HDR/EXR passthrough staging (T-015).
//!
//! `.hdr` and `.exr` inputs skip the TIF pipeline entirely and are staged into
//! the output directory as Radiance `.hdr`, so RC can treat them as its special
//! cubemap-HDR case in CryEngine. `.hdr` is copied byte-for-byte; `.exr` is
//! decoded (full HDR range preserved — the `PlanarImage` path clamps to `0..=1`
//! and must not be used here) and re-encoded as Radiance `.hdr`. The user's
//! source file is never modified or deleted.

use std::{
    fs::File,
    io::{BufReader, BufWriter},
    path::{Path, PathBuf},
};

use image::{codecs::hdr::HdrEncoder, ImageFormat, ImageReader, Rgb};

use crate::error::{Result, TexprocError};

/// True for input extensions that bypass the TIF pipeline and stage as HDR.
pub fn is_passthrough_ext(ext: &str) -> bool {
    matches!(ext.to_ascii_lowercase().as_str(), "hdr" | "exr")
}

/// True when `path`'s extension is a passthrough format.
pub fn is_passthrough_path(path: &Path) -> bool {
    path.extension()
        .and_then(|ext| ext.to_str())
        .is_some_and(is_passthrough_ext)
}

/// Stage one passthrough input into `output_dir`, returning the written `.hdr`
/// path. `.hdr` is copied verbatim; `.exr` is transcoded to Radiance `.hdr`.
/// The source file is untouched.
pub fn stage_passthrough(src: &Path, output_dir: &Path) -> Result<PathBuf> {
    std::fs::create_dir_all(output_dir)?;
    let stem = src
        .file_stem()
        .and_then(|value| value.to_str())
        .ok_or_else(|| {
            TexprocError::new(format!("passthrough input has no file stem: {}", src.display()))
        })?;
    let dest = output_dir.join(format!("{stem}.hdr"));
    let ext = src
        .extension()
        .and_then(|value| value.to_str())
        .unwrap_or_default()
        .to_ascii_lowercase();
    match ext.as_str() {
        "hdr" => {
            std::fs::copy(src, &dest).map_err(|error| {
                TexprocError::new(format!("failed to copy {}: {error}", src.display()))
            })?;
        }
        "exr" => exr_to_hdr(src, &dest)?,
        other => {
            return Err(TexprocError::new(format!(
                "not a passthrough format: `.{other}`"
            )))
        }
    }
    Ok(dest)
}

/// Decode an OpenEXR and write it as Radiance `.hdr`, preserving the HDR range
/// (values above 1.0 survive — no `PlanarImage` clamp).
fn exr_to_hdr(src: &Path, dest: &Path) -> Result<()> {
    let reader = ImageReader::with_format(
        BufReader::new(File::open(src).map_err(|error| {
            TexprocError::new(format!("failed to open {}: {error}", src.display()))
        })?),
        ImageFormat::OpenExr,
    );
    let rgb = reader.decode()?.to_rgb32f();
    let (width, height) = (rgb.width(), rgb.height());
    let pixels = rgb.pixels().copied().collect::<Vec<Rgb<f32>>>();
    let writer = BufWriter::new(File::create(dest).map_err(|error| {
        TexprocError::new(format!("failed to create {}: {error}", dest.display()))
    })?);
    HdrEncoder::new(writer).encode(&pixels, width as usize, height as usize)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use std::sync::atomic::{AtomicU64, Ordering};

    use image::codecs::{hdr::HdrDecoder, openexr::OpenExrEncoder};
    use image::{DynamicImage, ExtendedColorType, ImageDecoder, ImageEncoder};
    // ImageDecoder brings `dimensions()`/`from_decoder` into scope.

    use super::*;

    static NEXT: AtomicU64 = AtomicU64::new(0);

    fn temp_dir() -> PathBuf {
        let serial = NEXT.fetch_add(1, Ordering::Relaxed);
        let dir = std::env::temp_dir().join(format!(
            "texproc-t015-{}-{serial}",
            std::process::id()
        ));
        std::fs::create_dir_all(&dir).unwrap();
        dir
    }

    /// Anchor 1: an EXR with known f32 values (including HDR values above 1.0)
    /// transcodes to Radiance `.hdr` and reads back within RGBE precision.
    #[test]
    fn exr_to_hdr_roundtrip_preserves_values_within_rgbe_precision() {
        let dir = temp_dir();
        let exr = dir.join("probe.exr");
        // Two pixels, RGB, spanning below and above 1.0 with non-power-of-two
        // values so RGBE's shared-exponent quantization is actually exercised.
        let samples: [f32; 6] = [0.3, 0.7, 1.3, 5.1, 2.9, 0.15];
        let bytes = samples
            .iter()
            .flat_map(|sample| sample.to_ne_bytes())
            .collect::<Vec<_>>();
        OpenExrEncoder::new(BufWriter::new(File::create(&exr).unwrap()))
            .write_image(&bytes, 2, 1, ExtendedColorType::Rgb32F)
            .unwrap();

        let hdr = stage_passthrough(&exr, &dir).unwrap();
        assert_eq!(hdr, dir.join("probe.hdr"));

        // Read the Radiance HDR back to f32 and compare within RGBE tolerance.
        let decoder = HdrDecoder::new(BufReader::new(File::open(&hdr).unwrap())).unwrap();
        assert_eq!(decoder.dimensions(), (2, 1));
        let decoded = DynamicImage::from_decoder(decoder).unwrap().to_rgb32f();
        for pixel_index in 0..2u32 {
            let expected = &samples[pixel_index as usize * 3..pixel_index as usize * 3 + 3];
            let actual = decoded.get_pixel(pixel_index, 0).0;
            // RGBE stores one 8-bit exponent per pixel, so every channel's
            // absolute step is set by the pixel's largest channel. The error
            // bound is therefore (pixel max) / 128, not per-channel.
            let pixel_max = expected.iter().fold(0.0f32, |m, v| m.max(v.abs()));
            let tolerance = (pixel_max / 128.0).max(1.0 / 128.0);
            for channel in 0..3 {
                let delta = (actual[channel] - expected[channel]).abs();
                eprintln!(
                    "rgbe px{pixel_index} ch{channel}: expected {} -> {} (|Δ|={delta:.6}, tol={tolerance:.6})",
                    expected[channel], actual[channel]
                );
                assert!(
                    delta <= tolerance,
                    "px{pixel_index} ch{channel}: {} vs {} (tol {tolerance})",
                    actual[channel],
                    expected[channel]
                );
            }
        }
        std::fs::remove_dir_all(&dir).ok();
    }

    /// Anchor 1: `.hdr` passthrough is a byte-identical copy.
    #[test]
    fn hdr_passthrough_is_byte_identical_copy() {
        let dir = temp_dir();
        let src = dir.join("sky.hdr");
        // Encode a tiny valid Radiance HDR to copy.
        let pixels = vec![Rgb([1.5f32, 0.5, 3.0]); 4];
        HdrEncoder::new(BufWriter::new(File::create(&src).unwrap()))
            .encode(&pixels, 4, 1)
            .unwrap();

        let out = dir.join("out");
        let staged = stage_passthrough(&src, &out).unwrap();
        assert_eq!(staged, out.join("sky.hdr"));
        assert_eq!(
            std::fs::read(&src).unwrap(),
            std::fs::read(&staged).unwrap(),
            "hdr passthrough must be a byte-identical copy"
        );
        // Source untouched (still present and readable).
        assert!(src.is_file());
        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn passthrough_extension_predicate_is_case_insensitive() {
        assert!(is_passthrough_ext("hdr"));
        assert!(is_passthrough_ext("HDR"));
        assert!(is_passthrough_ext("exr"));
        assert!(is_passthrough_ext("Exr"));
        assert!(!is_passthrough_ext("png"));
        assert!(!is_passthrough_ext("tif"));
        assert!(is_passthrough_path(Path::new(r"C:\a\sky.HDR")));
        assert!(!is_passthrough_path(Path::new(r"C:\a\wall_diff.png")));
    }
}
