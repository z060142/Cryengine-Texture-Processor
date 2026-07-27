use crate::error::{Result, TexprocError};

#[derive(Clone, Debug, PartialEq)]
pub struct PlanarImage {
    pub width: u32,
    pub height: u32,
    pub planes: Vec<Vec<f32>>,
}

impl PlanarImage {
    pub fn new(width: u32, height: u32, planes: Vec<Vec<f32>>) -> Result<Self> {
        if width == 0 || height == 0 {
            return Err(TexprocError::new("image dimensions must be non-zero"));
        }
        if !(1..=4).contains(&planes.len()) {
            return Err(TexprocError::new(format!(
                "planar images require 1 to 4 channels, got {}",
                planes.len()
            )));
        }

        let expected_len = pixel_count(width, height)?;
        for (channel, plane) in planes.iter().enumerate() {
            if plane.len() != expected_len {
                return Err(TexprocError::new(format!(
                    "channel {channel} has {} samples, expected {expected_len}",
                    plane.len()
                )));
            }
            if plane.iter().any(|value| !value.is_finite()) {
                return Err(TexprocError::new(format!(
                    "channel {channel} contains a non-finite sample"
                )));
            }
            if plane.iter().any(|value| !(0.0..=1.0).contains(value)) {
                return Err(TexprocError::new(format!(
                    "channel {channel} contains a sample outside 0..=1"
                )));
            }
        }

        Ok(Self {
            width,
            height,
            planes,
        })
    }

    pub fn channels(&self) -> usize {
        self.planes.len()
    }

    pub fn pixel_count(&self) -> usize {
        self.planes[0].len()
    }

    pub fn from_interleaved_u8(
        width: u32,
        height: u32,
        channels: usize,
        samples: &[u8],
    ) -> Result<Self> {
        from_interleaved(width, height, channels, samples, |sample| {
            f32::from(*sample) / 255.0
        })
    }

    pub fn from_interleaved_u16(
        width: u32,
        height: u32,
        channels: usize,
        samples: &[u16],
    ) -> Result<Self> {
        from_interleaved(width, height, channels, samples, |sample| {
            f32::from(*sample) / 65535.0
        })
    }

    pub fn from_interleaved_f32(
        width: u32,
        height: u32,
        channels: usize,
        samples: &[f32],
    ) -> Result<Self> {
        from_interleaved(width, height, channels, samples, |sample| {
            if sample.is_finite() {
                sample.clamp(0.0, 1.0)
            } else {
                f32::NAN
            }
        })
    }

    pub fn to_interleaved_u8(&self) -> Vec<u8> {
        let mut output = Vec::with_capacity(self.pixel_count() * self.channels());
        for index in 0..self.pixel_count() {
            for plane in &self.planes {
                output.push(quantize_u8(plane[index]));
            }
        }
        output
    }
}

pub fn quantize_u8(value: f32) -> u8 {
    (value.clamp(0.0, 1.0) * 255.0).round() as u8
}

fn pixel_count(width: u32, height: u32) -> Result<usize> {
    let count = u64::from(width)
        .checked_mul(u64::from(height))
        .ok_or_else(|| TexprocError::new("image dimensions overflow"))?;
    usize::try_from(count).map_err(|_| TexprocError::new("image is too large for this platform"))
}

fn from_interleaved<T>(
    width: u32,
    height: u32,
    channels: usize,
    samples: &[T],
    convert: impl Fn(&T) -> f32,
) -> Result<PlanarImage> {
    if !(1..=4).contains(&channels) {
        return Err(TexprocError::new(format!(
            "interleaved images require 1 to 4 channels, got {channels}"
        )));
    }
    let count = pixel_count(width, height)?;
    let expected = count
        .checked_mul(channels)
        .ok_or_else(|| TexprocError::new("interleaved sample count overflow"))?;
    if samples.len() != expected {
        return Err(TexprocError::new(format!(
            "interleaved buffer has {} samples, expected {expected}",
            samples.len()
        )));
    }

    let mut planes = (0..channels)
        .map(|_| Vec::with_capacity(count))
        .collect::<Vec<_>>();
    for pixel in samples.chunks_exact(channels) {
        for (channel, sample) in pixel.iter().enumerate() {
            planes[channel].push(convert(sample));
        }
    }
    PlanarImage::new(width, height, planes)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn u8_f32_u8_round_trip_is_exact_for_all_values() {
        let values = (0..=u8::MAX).collect::<Vec<_>>();
        let image = PlanarImage::from_interleaved_u8(256, 1, 1, &values).unwrap();
        assert_eq!(image.to_interleaved_u8(), values);
    }

    #[test]
    fn constructor_rejects_invalid_shape_and_domain() {
        assert!(PlanarImage::new(0, 1, vec![vec![]]).is_err());
        assert!(PlanarImage::new(1, 1, vec![vec![0.0], vec![], vec![0.0]]).is_err());
        assert!(PlanarImage::new(1, 1, vec![vec![1.01]]).is_err());
        assert!(PlanarImage::new(1, 1, vec![vec![f32::NAN]]).is_err());
    }
}
