use image::{imageops::FilterType, ImageBuffer, Luma};

use crate::{
    constants::LUMA_WEIGHTS,
    error::{Result, TexprocError},
    planar::PlanarImage,
};

pub fn srgb_decode(value: f32) -> f32 {
    let value = value.clamp(0.0, 1.0);
    if value <= 0.04045 {
        value / 12.92
    } else {
        ((value + 0.055) / 1.055).powf(2.4)
    }
}

pub fn srgb_encode(value: f32) -> f32 {
    let value = value.clamp(0.0, 1.0);
    if value <= 0.003_130_8 {
        value * 12.92
    } else {
        1.055 * value.powf(1.0 / 2.4) - 0.055
    }
}

pub fn invert(image: &PlanarImage) -> PlanarImage {
    map_samples(image, |value| 1.0 - value)
}

pub fn gray(image: &PlanarImage) -> PlanarImage {
    let samples = (0..image.pixel_count())
        .map(|index| luma_at(image, index))
        .collect();
    PlanarImage::new(image.width, image.height, vec![samples])
        .expect("gray preserves valid dimensions and normalized samples")
}

pub fn linear_burn(first: &PlanarImage, second: &PlanarImage) -> Result<PlanarImage> {
    binary_per_channel(first, second, |a, b| (a + b - 1.0).max(0.0))
}

pub fn darken(first: &PlanarImage, second: &PlanarImage) -> Result<PlanarImage> {
    binary_per_channel(first, second, f32::min)
}

pub fn darker_color(first: &PlanarImage, second: &PlanarImage) -> Result<PlanarImage> {
    let channels = compatible_channels(first, second)?;
    let count = first.pixel_count();
    let mut planes = (0..channels)
        .map(|_| Vec::with_capacity(count))
        .collect::<Vec<_>>();

    for index in 0..count {
        let choose_first = luma_at(first, index) <= luma_at(second, index);
        for (channel, plane) in planes.iter_mut().enumerate() {
            plane.push(if choose_first {
                sample_at(first, channel, index)
            } else {
                sample_at(second, channel, index)
            });
        }
    }
    PlanarImage::new(first.width, first.height, planes)
}

pub fn multiply(first: &PlanarImage, second: &PlanarImage) -> Result<PlanarImage> {
    binary_per_channel(first, second, |a, b| a * b)
}

pub fn copy_opacity(destination: &PlanarImage, source: &PlanarImage) -> Result<PlanarImage> {
    ensure_same_dimensions(destination, source)?;
    let mut output = destination.clone();
    let alpha = (0..source.pixel_count())
        .map(|index| luma_at(source, index))
        .collect::<Vec<_>>();

    match output.channels() {
        1 | 3 => output.planes.push(alpha),
        2 => output.planes[1] = alpha,
        4 => output.planes[3] = alpha,
        _ => unreachable!("PlanarImage constrains channel count"),
    }
    Ok(output)
}

pub fn flip_green(image: &PlanarImage) -> Result<PlanarImage> {
    if image.channels() < 3 {
        return Err(TexprocError::new("OP-FLIPG requires an RGB or RGBA image"));
    }
    let mut output = image.clone();
    for value in &mut output.planes[1] {
        *value = 1.0 - *value;
    }
    Ok(output)
}

pub fn resize(image: &PlanarImage, max_dimension: u32) -> Result<PlanarImage> {
    if max_dimension == 0 {
        return Err(TexprocError::new(
            "OP-RESIZE max dimension must be non-zero",
        ));
    }
    let current_max = image.width.max(image.height);
    if current_max <= max_dimension {
        return Ok(image.clone());
    }

    let scale = f64::from(max_dimension) / f64::from(current_max);
    let target_width = (f64::from(image.width) * scale).round().max(1.0) as u32;
    let target_height = (f64::from(image.height) * scale).round().max(1.0) as u32;
    let mut planes = Vec::with_capacity(image.channels());

    for plane in &image.planes {
        let buffer =
            ImageBuffer::<Luma<f32>, Vec<f32>>::from_raw(image.width, image.height, plane.clone())
                .expect("plane length was validated by PlanarImage");
        let resized =
            image::imageops::resize(&buffer, target_width, target_height, FilterType::Lanczos3);
        planes.push(resized.into_raw());
    }
    PlanarImage::new(target_width, target_height, planes)
}

pub fn auto_level(image: &PlanarImage) -> PlanarImage {
    let planes = image
        .planes
        .iter()
        .map(|plane| {
            let minimum = plane.iter().copied().fold(f32::INFINITY, f32::min);
            let maximum = plane.iter().copied().fold(f32::NEG_INFINITY, f32::max);
            let range = maximum - minimum;
            if range <= f32::EPSILON {
                plane.clone()
            } else {
                plane
                    .iter()
                    .map(|value| (value - minimum) / range)
                    .collect()
            }
        })
        .collect();
    PlanarImage::new(image.width, image.height, planes)
        .expect("auto-level preserves valid normalized samples")
}

pub fn eval_mul(image: &PlanarImage, factor: f32) -> Result<PlanarImage> {
    if !factor.is_finite() {
        return Err(TexprocError::new(
            "OP-EVALMUL factor must be a finite number",
        ));
    }
    Ok(map_samples(image, |value| (value * factor).clamp(0.0, 1.0)))
}

pub fn normal_from_height(image: &PlanarImage, strength: f32) -> Result<PlanarImage> {
    if !strength.is_finite() {
        return Err(TexprocError::new(
            "OP-NORMALFROMHEIGHT strength must be finite",
        ));
    }
    let height = gray(image);
    let width = image.width as i32;
    let image_height = image.height as i32;
    let mut red = Vec::with_capacity(image.pixel_count());
    let mut green = Vec::with_capacity(image.pixel_count());
    let mut blue = Vec::with_capacity(image.pixel_count());

    let sample = |x: i32, y: i32| {
        let x = x.clamp(0, width - 1) as u32;
        let y = y.clamp(0, image_height - 1) as u32;
        height.planes[0][(y * image.width + x) as usize]
    };

    for y in 0..image_height {
        for x in 0..width {
            let top_left = sample(x - 1, y - 1);
            let top = sample(x, y - 1);
            let top_right = sample(x + 1, y - 1);
            let left = sample(x - 1, y);
            let right = sample(x + 1, y);
            let bottom_left = sample(x - 1, y + 1);
            let bottom = sample(x, y + 1);
            let bottom_right = sample(x + 1, y + 1);

            let gradient_x =
                -top_left + top_right - 2.0 * left + 2.0 * right - bottom_left + bottom_right;
            let gradient_y =
                -top_left - 2.0 * top - top_right + bottom_left + 2.0 * bottom + bottom_right;

            let nx = -gradient_x * strength;
            let ny = -gradient_y * strength;
            let nz = 1.0;
            let inverse_length = (nx * nx + ny * ny + nz * nz).sqrt().recip();
            red.push(nx * inverse_length * 0.5 + 0.5);
            green.push(ny * inverse_length * 0.5 + 0.5);
            blue.push(nz * inverse_length * 0.5 + 0.5);
        }
    }
    PlanarImage::new(image.width, image.height, vec![red, green, blue])
}

pub fn colorize(image: &PlanarImage, black: [f32; 3], white: [f32; 3]) -> Result<PlanarImage> {
    if black
        .into_iter()
        .chain(white)
        .any(|value| !value.is_finite() || !(0.0..=1.0).contains(&value))
    {
        return Err(TexprocError::new(
            "OP-COLORIZE endpoints must be finite values in 0..=1",
        ));
    }

    let grayscale = gray(image);
    let mut planes = vec![
        Vec::with_capacity(image.pixel_count()),
        Vec::with_capacity(image.pixel_count()),
        Vec::with_capacity(image.pixel_count()),
    ];
    for value in &grayscale.planes[0] {
        for channel in 0..3 {
            planes[channel].push(black[channel] + (white[channel] - black[channel]) * value);
        }
    }
    PlanarImage::new(image.width, image.height, planes)
}

fn map_samples(image: &PlanarImage, operation: impl Fn(f32) -> f32) -> PlanarImage {
    let planes = image
        .planes
        .iter()
        .map(|plane| plane.iter().copied().map(&operation).collect())
        .collect();
    PlanarImage::new(image.width, image.height, planes)
        .expect("sample operation preserves valid dimensions and normalized samples")
}

fn binary_per_channel(
    first: &PlanarImage,
    second: &PlanarImage,
    operation: impl Fn(f32, f32) -> f32,
) -> Result<PlanarImage> {
    let channels = compatible_channels(first, second)?;
    let mut planes = (0..channels)
        .map(|_| Vec::with_capacity(first.pixel_count()))
        .collect::<Vec<_>>();
    for index in 0..first.pixel_count() {
        for (channel, plane) in planes.iter_mut().enumerate() {
            plane.push(operation(
                sample_at(first, channel, index),
                sample_at(second, channel, index),
            ));
        }
    }
    PlanarImage::new(first.width, first.height, planes)
}

fn compatible_channels(first: &PlanarImage, second: &PlanarImage) -> Result<usize> {
    ensure_same_dimensions(first, second)?;
    if first.channels() == second.channels() {
        Ok(first.channels())
    } else if first.channels() == 1 || second.channels() == 1 {
        Ok(first.channels().max(second.channels()))
    } else {
        Err(TexprocError::new(format!(
            "channel mismatch: {} versus {}; only single-channel broadcast is supported",
            first.channels(),
            second.channels()
        )))
    }
}

fn ensure_same_dimensions(first: &PlanarImage, second: &PlanarImage) -> Result<()> {
    if first.width != second.width || first.height != second.height {
        return Err(TexprocError::new(format!(
            "dimension mismatch: {}x{} versus {}x{}",
            first.width, first.height, second.width, second.height
        )));
    }
    Ok(())
}

fn sample_at(image: &PlanarImage, channel: usize, index: usize) -> f32 {
    if image.channels() == 1 {
        image.planes[0][index]
    } else {
        image.planes[channel][index]
    }
}

fn luma_at(image: &PlanarImage, index: usize) -> f32 {
    if image.channels() < 3 {
        image.planes[0][index]
    } else {
        LUMA_WEIGHTS[0] * image.planes[0][index]
            + LUMA_WEIGHTS[1] * image.planes[1][index]
            + LUMA_WEIGHTS[2] * image.planes[2][index]
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn mono(values: &[f32], width: u32, height: u32) -> PlanarImage {
        PlanarImage::new(width, height, vec![values.to_vec()]).unwrap()
    }

    fn rgb(red: f32, green: f32, blue: f32) -> PlanarImage {
        PlanarImage::new(1, 1, vec![vec![red], vec![green], vec![blue]]).unwrap()
    }

    fn assert_close(actual: f32, expected: f32) {
        assert!(
            (actual - expected).abs() <= 1.0e-6,
            "{actual} != {expected}"
        );
    }

    #[test]
    fn op_invert_covers_zero_one_and_one_by_one() {
        let output = invert(&mono(&[0.0, 1.0], 2, 1));
        assert_eq!(output.planes[0], vec![1.0, 0.0]);
        assert_eq!(invert(&mono(&[0.25], 1, 1)).planes[0], vec![0.75]);
    }

    #[test]
    fn op_gray_uses_bt601_at_boundaries() {
        assert_close(gray(&rgb(1.0, 0.0, 0.0)).planes[0][0], 0.299);
        assert_eq!(gray(&rgb(0.0, 0.0, 0.0)).planes[0][0], 0.0);
        assert_eq!(gray(&rgb(1.0, 1.0, 1.0)).planes[0][0], 1.0);
    }

    #[test]
    fn op_linear_burn_clamps_at_zero() {
        let dark = linear_burn(&mono(&[0.0], 1, 1), &mono(&[1.0], 1, 1)).unwrap();
        let light = linear_burn(&mono(&[1.0], 1, 1), &mono(&[1.0], 1, 1)).unwrap();
        assert_eq!(dark.planes[0][0], 0.0);
        assert_eq!(light.planes[0][0], 1.0);
    }

    #[test]
    fn op_darken_selects_per_channel_minimum() {
        let output = darken(&rgb(0.0, 0.8, 1.0), &rgb(1.0, 0.2, 0.0)).unwrap();
        assert_eq!(output, rgb(0.0, 0.2, 0.0));
    }

    #[test]
    fn op_darker_color_selects_entire_darker_rgb_tuple() {
        let first = rgb(1.0, 0.0, 0.0);
        let second = rgb(0.0, 0.4, 0.0);
        assert_eq!(darker_color(&first, &second).unwrap(), second);
        assert_eq!(
            darker_color(&rgb(0.0, 0.0, 0.0), &rgb(1.0, 1.0, 1.0)).unwrap(),
            rgb(0.0, 0.0, 0.0)
        );
    }

    #[test]
    fn op_multiply_supports_gray_broadcast_and_boundaries() {
        let output = multiply(&rgb(0.0, 0.5, 1.0), &mono(&[0.5], 1, 1)).unwrap();
        assert_eq!(output, rgb(0.0, 0.25, 0.5));
    }

    #[test]
    fn op_copy_opacity_writes_luma_without_inversion() {
        let output = copy_opacity(&rgb(0.0, 1.0, 0.0), &rgb(1.0, 1.0, 1.0)).unwrap();
        assert_eq!(output.channels(), 4);
        assert_eq!(output.planes[3][0], 1.0);
        let zero = copy_opacity(&mono(&[1.0], 1, 1), &mono(&[0.0], 1, 1)).unwrap();
        assert_eq!(zero.planes[1][0], 0.0);
    }

    #[test]
    fn op_flip_green_only_inverts_green() {
        assert_eq!(flip_green(&rgb(0.0, 0.0, 1.0)).unwrap(), rgb(0.0, 1.0, 1.0));
        assert_eq!(flip_green(&rgb(1.0, 1.0, 0.0)).unwrap(), rgb(1.0, 0.0, 0.0));
        assert!(flip_green(&mono(&[0.0], 1, 1)).is_err());
    }

    #[test]
    fn op_resize_is_lanczos_and_never_upscales() {
        let small = mono(&[0.25], 1, 1);
        assert_eq!(resize(&small, 8).unwrap(), small);
        let large = mono(&[0.0, 1.0, 1.0, 0.0], 4, 1);
        let output = resize(&large, 2).unwrap();
        assert_eq!((output.width, output.height), (2, 1));
        assert!(output.planes[0]
            .iter()
            .all(|value| (0.0..=1.0).contains(value)));
        assert!(resize(&large, 0).is_err());
    }

    #[test]
    fn op_auto_level_stretches_each_plane_and_preserves_constant_one_by_one() {
        let output = auto_level(&mono(&[0.25, 0.75], 2, 1));
        assert_eq!(output.planes[0], vec![0.0, 1.0]);
        assert_eq!(auto_level(&mono(&[1.0], 1, 1)).planes[0], vec![1.0]);
    }

    #[test]
    fn op_eval_mul_clamps_zero_and_one() {
        let output = eval_mul(&mono(&[0.0, 0.75, 1.0], 3, 1), 2.0).unwrap();
        assert_eq!(output.planes[0], vec![0.0, 1.0, 1.0]);
        assert_eq!(
            eval_mul(&mono(&[1.0], 1, 1), 0.0).unwrap().planes[0][0],
            0.0
        );
    }

    #[test]
    fn op_normal_from_height_handles_flat_one_by_one_and_sobel_slope() {
        let flat = normal_from_height(&mono(&[0.0], 1, 1), 10.0).unwrap();
        assert_eq!(flat, rgb(0.5, 0.5, 1.0));
        assert_eq!(normal_from_height(&mono(&[1.0], 1, 1), 10.0).unwrap(), flat);

        let slope = normal_from_height(&mono(&[0.0, 0.5, 1.0], 3, 1), 1.0).unwrap();
        assert_ne!(slope.planes[0][1], 0.5);
        assert!((0.5..=1.0).contains(&slope.planes[2][1]));
    }

    #[test]
    fn op_colorize_lerps_endpoints_and_midpoint() {
        let output = colorize(
            &mono(&[0.0, 0.5, 1.0], 3, 1),
            [0.0, 0.0, 0.0],
            [1.0, 0.5, 0.0],
        )
        .unwrap();
        assert_eq!(output.planes[0], vec![0.0, 0.5, 1.0]);
        assert_eq!(output.planes[1], vec![0.0, 0.25, 0.5]);
        assert_eq!(output.planes[2], vec![0.0, 0.0, 0.0]);
    }

    #[test]
    fn srgb_helpers_round_trip_f32_domain() {
        for index in 0..=1000 {
            let encoded = index as f32 / 1000.0;
            assert_close(srgb_encode(srgb_decode(encoded)), encoded);
        }
    }
}
