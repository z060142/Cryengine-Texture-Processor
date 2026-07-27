use std::{
    fs,
    path::{Path, PathBuf},
};

use ce_schema::texture_suffix;

use crate::{
    constants::{
        DEFAULT_NONMETAL_REFLECTION, DEFAULT_SSS_COLOR, DEFAULT_TEXTURE_SIZE, SSS_COLORIZE_WHITE,
    },
    error::{Result, TexprocError},
    io::write_tiff_lzw,
    ops::{
        auto_level, colorize, copy_opacity, eval_mul, flip_green, gray, resize, resize_to,
        srgb_decode, srgb_encode,
    },
    pipeline::{ArmOrder, IntermediateSettings, MetalGate, TextureGroup},
    planar::PlanarImage,
};

#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub enum OutputResolution {
    #[default]
    Original,
    Max(u32),
}

#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub enum DiffFormat {
    #[default]
    Albedo,
    DiffuseAo,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct TextureTypeSettings {
    pub diff: bool,
    pub spec: bool,
    pub ddna: bool,
    pub displ: bool,
    pub emissive: bool,
    pub sss: bool,
}

impl Default for TextureTypeSettings {
    fn default() -> Self {
        Self {
            diff: true,
            spec: true,
            ddna: true,
            displ: true,
            emissive: true,
            sss: true,
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct TextureSettings {
    pub output_resolution: OutputResolution,
    pub diff_format: DiffFormat,
    pub normal_flip_green: bool,
    pub normalize_height: bool,
    pub process_metallic: bool,
    pub metal_gate: bool,
    pub metal_gate_metallic_cut: f32,
    pub metal_gate_spec_min: f32,
    pub metal_gate_gloss_cut: f32,
    pub metal_gate_transition: f32,
    pub normal_from_height_strength: f32,
    pub arm_order: ArmOrder,
    pub generate_missing_spec: bool,
    pub generate_missing_emissive: bool,
    pub generate_missing_sss: bool,
    pub generate_sss_from_diffuse: bool,
    pub emissive_brightness: f32,
    pub sss_intensity: f32,
    pub sss_contrast: f32,
    pub dither: bool,
    pub texture_types: TextureTypeSettings,
}

impl Default for TextureSettings {
    fn default() -> Self {
        Self {
            output_resolution: OutputResolution::Original,
            diff_format: DiffFormat::Albedo,
            normal_flip_green: false,
            normalize_height: false,
            process_metallic: true,
            metal_gate: true,
            metal_gate_metallic_cut: 0.5,
            metal_gate_spec_min: 180.0 / 255.0,
            metal_gate_gloss_cut: 0.0,
            metal_gate_transition: 0.05,
            normal_from_height_strength: 10.0,
            arm_order: ArmOrder::Arm,
            generate_missing_spec: true,
            generate_missing_emissive: false,
            generate_missing_sss: false,
            generate_sss_from_diffuse: false,
            emissive_brightness: 1.0,
            sss_intensity: 1.0,
            sss_contrast: 0.8,
            dither: false,
            texture_types: TextureTypeSettings::default(),
        }
    }
}

impl TextureSettings {
    pub fn intermediate_settings(&self) -> IntermediateSettings {
        IntermediateSettings {
            process_metallic: self.process_metallic,
            normal_from_height_strength: self.normal_from_height_strength,
            arm_order: self.arm_order,
            metal_gate: MetalGate {
                enabled: self.metal_gate,
                metallic_cut: self.metal_gate_metallic_cut,
                spec_min: self.metal_gate_spec_min,
                gloss_cut: self.metal_gate_gloss_cut,
                transition: self.metal_gate_transition,
            },
        }
    }
}

#[derive(Clone, Debug, PartialEq)]
pub struct OutputImage {
    pub filename: String,
    pub image: PlanarImage,
}

#[derive(Clone, Debug, Default, PartialEq)]
pub struct OutputTextures {
    pub diff: Option<OutputImage>,
    pub spec: Option<OutputImage>,
    pub ddna: Option<OutputImage>,
    pub displ: Option<OutputImage>,
    pub emissive: Option<OutputImage>,
    pub sss: Option<OutputImage>,
}

impl OutputTextures {
    fn iter(&self) -> impl Iterator<Item = &OutputImage> {
        [
            self.diff.as_ref(),
            self.spec.as_ref(),
            self.ddna.as_ref(),
            self.displ.as_ref(),
            self.emissive.as_ref(),
            self.sss.as_ref(),
        ]
        .into_iter()
        .flatten()
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Stage2Step {
    Diff,
    Spec,
    Ddna,
    Displ,
    Emissive,
    Sss,
}

#[derive(Clone, Debug, Default, Eq, PartialEq)]
pub struct Stage2Report {
    pub trace: Vec<Stage2Step>,
    pub produced: Vec<String>,
}

pub fn process_stage2(
    group: &mut TextureGroup,
    settings: &TextureSettings,
) -> Result<Stage2Report> {
    validate_settings(settings)?;
    let mut output = OutputTextures::default();
    let mut report = Stage2Report::default();

    if settings.texture_types.diff {
        report.trace.push(Stage2Step::Diff);
        output.diff = export_diff(group, settings)?;
    }
    if settings.texture_types.spec {
        report.trace.push(Stage2Step::Spec);
        output.spec = export_spec(group, settings)?;
    }
    if settings.texture_types.ddna {
        report.trace.push(Stage2Step::Ddna);
        output.ddna = export_ddna(group, settings)?;
    }
    if settings.texture_types.displ {
        report.trace.push(Stage2Step::Displ);
        output.displ = export_displ(group, settings)?;
    }
    if settings.texture_types.emissive {
        report.trace.push(Stage2Step::Emissive);
        output.emissive = export_emissive(group, settings)?;
    }
    if settings.texture_types.sss {
        report.trace.push(Stage2Step::Sss);
        output.sss = export_sss(group, settings)?;
    }

    report.produced = output.iter().map(|item| item.filename.clone()).collect();
    group.output = output;
    Ok(report)
}

pub fn write_stage2_outputs(
    output: &OutputTextures,
    output_directory: impl AsRef<Path>,
) -> Result<Vec<PathBuf>> {
    let output_directory = output_directory.as_ref();
    fs::create_dir_all(output_directory)?;
    let mut written = Vec::new();
    for item in output.iter() {
        let path = output_directory.join(&item.filename);
        write_tiff_lzw(&path, &item.image)?;
        written.push(path);
    }
    Ok(written)
}

/// Streaming variant of `process_stage2` + `write_stage2_outputs` for the batch
/// path: each output is generated, written to disk, and its buffer dropped
/// immediately instead of accumulating all six in an `OutputTextures` before
/// writing. Bytes are identical to the two-step path (same export functions,
/// same order, same `write_tiff_lzw`); only the peak working set differs.
pub fn process_and_write_stage2(
    group: &TextureGroup,
    settings: &TextureSettings,
    output_directory: impl AsRef<Path>,
) -> Result<Vec<PathBuf>> {
    validate_settings(settings)?;
    let directory = output_directory.as_ref();
    fs::create_dir_all(directory)?;
    let mut written = Vec::new();
    let types = settings.texture_types;
    if types.diff {
        write_optional(directory, export_diff(group, settings)?, &mut written)?;
    }
    if types.spec {
        write_optional(directory, export_spec(group, settings)?, &mut written)?;
    }
    if types.ddna {
        write_optional(directory, export_ddna(group, settings)?, &mut written)?;
    }
    if types.displ {
        write_optional(directory, export_displ(group, settings)?, &mut written)?;
    }
    if types.emissive {
        write_optional(directory, export_emissive(group, settings)?, &mut written)?;
    }
    if types.sss {
        write_optional(directory, export_sss(group, settings)?, &mut written)?;
    }
    Ok(written)
}

fn write_optional(
    directory: &Path,
    image: Option<OutputImage>,
    written: &mut Vec<PathBuf>,
) -> Result<()> {
    if let Some(image) = image {
        let path = directory.join(&image.filename);
        write_tiff_lzw(&path, &image.image)?;
        written.push(path);
        // `image` is dropped here, before the next output is generated.
    }
    Ok(())
}

fn validate_settings(settings: &TextureSettings) -> Result<()> {
    if matches!(settings.output_resolution, OutputResolution::Max(0)) {
        return Err(TexprocError::new(
            "output resolution must be non-zero or original",
        ));
    }
    for (name, value) in [
        ("emissive_brightness", settings.emissive_brightness),
        ("sss_intensity", settings.sss_intensity),
        ("sss_contrast", settings.sss_contrast),
    ] {
        if !value.is_finite() {
            return Err(TexprocError::new(format!("{name} must be finite")));
        }
    }
    Ok(())
}

fn export_diff(group: &TextureGroup, settings: &TextureSettings) -> Result<Option<OutputImage>> {
    let base = group
        .intermediate
        .albedo
        .as_ref()
        .or_else(|| source_image(group, SourceSlot::Diffuse));
    let Some(base) = base else {
        return Ok(None);
    };

    let mut image = resize_for_output(base, settings.output_resolution)?;
    if settings.diff_format == DiffFormat::DiffuseAo {
        let ao = group
            .intermediate
            .ao
            .as_ref()
            .or_else(|| source_image(group, SourceSlot::Ao));
        if let Some(ao) = ao {
            // Secondary source: force-fit onto the primary's working grid (T-017).
            let ao = resize_to(&gray(ao), image.width, image.height)?;
            image = multiply_ao_linear(&image, &ao)?;
        }
    }
    if let Some(alpha) = source_image(group, SourceSlot::Alpha) {
        let alpha = resize_to(&gray(alpha), image.width, image.height)?;
        image = copy_opacity(&image, &alpha)?;
    }

    Ok(Some(named_output(&group.base_name, "diff", false, image)?))
}

fn export_spec(group: &TextureGroup, settings: &TextureSettings) -> Result<Option<OutputImage>> {
    if let Some(source) = group
        .intermediate
        .reflection
        .as_ref()
        .or_else(|| source_image(group, SourceSlot::Specular))
    {
        let image = resize_for_output(source, settings.output_resolution)?;
        return Ok(Some(named_output(&group.base_name, "spec", false, image)?));
    }
    if !settings.generate_missing_spec {
        return Ok(None);
    }

    let (width, height) = fallback_dimensions(group);
    let image = flat_rgb(width, height, DEFAULT_NONMETAL_REFLECTION)?;
    let image = resize_for_output(&image, settings.output_resolution)?;
    Ok(Some(named_output(&group.base_name, "spec", false, image)?))
}

fn export_ddna(group: &TextureGroup, settings: &TextureSettings) -> Result<Option<OutputImage>> {
    let normal = group
        .intermediate
        .normal
        .as_ref()
        .or_else(|| source_image(group, SourceSlot::Normal));
    let Some(normal) = normal else {
        return Ok(None);
    };

    let mut image = to_rgb(&resize_for_output(normal, settings.output_resolution)?)?;
    if settings.normal_flip_green {
        image = flip_green(&image)?;
    }

    let has_gloss = group.intermediate.glossiness.is_some();
    if let Some(glossiness) = &group.intermediate.glossiness {
        // Secondary source: force-fit onto the normal's working grid (T-017).
        let glossiness = resize_to(&gray(glossiness), image.width, image.height)?;
        image = copy_opacity(&image, &glossiness)?;
    }

    Ok(Some(named_output(
        &group.base_name,
        "ddna",
        has_gloss,
        image,
    )?))
}

fn export_displ(group: &TextureGroup, settings: &TextureSettings) -> Result<Option<OutputImage>> {
    let height = group
        .intermediate
        .height
        .as_ref()
        .or_else(|| source_image(group, SourceSlot::Displacement))
        .or_else(|| source_image(group, SourceSlot::Height));
    let Some(height) = height else {
        return Ok(None);
    };

    let mut image = resize_for_output(height, settings.output_resolution)?;
    if settings.normalize_height {
        image = auto_level(&image);
    }
    let grayscale = gray(&image);
    let plane = grayscale.planes[0].clone();
    let image = PlanarImage::new(
        grayscale.width,
        grayscale.height,
        vec![plane.clone(), plane.clone(), plane.clone(), plane],
    )?;
    Ok(Some(named_output(&group.base_name, "displ", false, image)?))
}

fn export_emissive(
    group: &TextureGroup,
    settings: &TextureSettings,
) -> Result<Option<OutputImage>> {
    let image = if let Some(source) = source_image(group, SourceSlot::Emissive) {
        let source = resize_for_output(source, settings.output_resolution)?;
        eval_mul(&source, settings.emissive_brightness.clamp(0.1, 5.0))?
    } else if settings.generate_missing_emissive {
        let (width, height) = fallback_dimensions(group);
        let fallback = flat_rgb(width, height, [0.0; 3])?;
        resize_for_output(&fallback, settings.output_resolution)?
    } else {
        return Ok(None);
    };

    Ok(Some(named_output(
        &group.base_name,
        "emissive",
        false,
        image,
    )?))
}

fn export_sss(group: &TextureGroup, settings: &TextureSettings) -> Result<Option<OutputImage>> {
    let image = if let Some(source) = source_image(group, SourceSlot::Sss) {
        let source = resize_for_output(source, settings.output_resolution)?;
        eval_mul(&source, settings.sss_intensity.clamp(0.1, 3.0))?
    } else if settings.generate_sss_from_diffuse {
        let source = group
            .intermediate
            .albedo
            .as_ref()
            .or_else(|| source_image(group, SourceSlot::Diffuse));
        if let Some(source) = source {
            let source = resize_for_output(source, settings.output_resolution)?;
            let colored = colorize(&gray(&source), [0.0; 3], SSS_COLORIZE_WHITE)?;
            contrast(&colored, settings.sss_contrast)
        } else if settings.generate_missing_sss {
            default_sss(group, settings.output_resolution)?
        } else {
            return Ok(None);
        }
    } else if settings.generate_missing_sss {
        default_sss(group, settings.output_resolution)?
    } else {
        return Ok(None);
    };

    Ok(Some(named_output(&group.base_name, "sss", false, image)?))
}

fn default_sss(group: &TextureGroup, resolution: OutputResolution) -> Result<PlanarImage> {
    let (width, height) = fallback_dimensions(group);
    let fallback = flat_rgb(width, height, DEFAULT_SSS_COLOR)?;
    resize_for_output(&fallback, resolution)
}

fn resize_for_output(image: &PlanarImage, resolution: OutputResolution) -> Result<PlanarImage> {
    match resolution {
        OutputResolution::Original => Ok(image.clone()),
        OutputResolution::Max(maximum) => resize(image, maximum),
    }
}

fn multiply_ao_linear(base: &PlanarImage, ao: &PlanarImage) -> Result<PlanarImage> {
    if base.width != ao.width || base.height != ao.height {
        return Err(TexprocError::new(format!(
            "OUT-DIFF dimension mismatch after resize: base {}x{} versus AO {}x{}",
            base.width, base.height, ao.width, ao.height
        )));
    }
    if ao.channels() != 1 {
        return Err(TexprocError::new("OUT-DIFF AO must be grayscale"));
    }

    let mut output = base.clone();
    let color_channels = if output.channels() >= 3 { 3 } else { 1 };
    for channel in 0..color_channels {
        for index in 0..output.pixel_count() {
            output.planes[channel][index] =
                srgb_encode(srgb_decode(output.planes[channel][index]) * ao.planes[0][index]);
        }
    }
    Ok(output)
}

fn contrast(image: &PlanarImage, factor: f32) -> PlanarImage {
    let pivot = gray(image).planes[0].iter().sum::<f32>() / image.pixel_count() as f32;
    let planes = image
        .planes
        .iter()
        .map(|plane| {
            plane
                .iter()
                .map(|value| (pivot + (value - pivot) * factor).clamp(0.0, 1.0))
                .collect()
        })
        .collect();
    PlanarImage::new(image.width, image.height, planes)
        .expect("contrast preserves dimensions and normalized finite samples")
}

fn fallback_dimensions(group: &TextureGroup) -> (u32, u32) {
    group
        .intermediate
        .albedo
        .as_ref()
        .or_else(|| source_image(group, SourceSlot::Diffuse))
        .map_or(
            (DEFAULT_TEXTURE_SIZE[0], DEFAULT_TEXTURE_SIZE[1]),
            |image| (image.width, image.height),
        )
}

fn flat_rgb(width: u32, height: u32, color: [f32; 3]) -> Result<PlanarImage> {
    let count = usize::try_from(u64::from(width) * u64::from(height))
        .map_err(|_| TexprocError::new("fallback image is too large"))?;
    PlanarImage::new(
        width,
        height,
        color.map(|value| vec![value; count]).to_vec(),
    )
}

fn to_rgb(image: &PlanarImage) -> Result<PlanarImage> {
    let planes = if image.channels() >= 3 {
        image.planes[..3].to_vec()
    } else {
        vec![image.planes[0].clone(); 3]
    };
    PlanarImage::new(image.width, image.height, planes)
}

fn named_output(
    base_name: &str,
    key: &str,
    normal_has_alpha: bool,
    image: PlanarImage,
) -> Result<OutputImage> {
    let suffix = texture_suffix(key, normal_has_alpha);
    if suffix.is_empty() {
        return Err(TexprocError::new(format!(
            "ce-schema has no output suffix for `{key}`"
        )));
    }
    Ok(OutputImage {
        filename: format!("{base_name}{suffix}.tif"),
        image,
    })
}

#[derive(Clone, Copy)]
enum SourceSlot {
    Diffuse,
    Normal,
    Specular,
    Displacement,
    Height,
    Ao,
    Alpha,
    Emissive,
    Sss,
}

fn source_image(group: &TextureGroup, slot: SourceSlot) -> Option<&PlanarImage> {
    match slot {
        SourceSlot::Diffuse => group.sources.diffuse.as_ref(),
        SourceSlot::Normal => group.sources.normal.as_ref(),
        SourceSlot::Specular => group.sources.specular.as_ref(),
        SourceSlot::Displacement => group.sources.displacement.as_ref(),
        SourceSlot::Height => group.sources.height.as_ref(),
        SourceSlot::Ao => group.sources.ao.as_ref(),
        SourceSlot::Alpha => group.sources.alpha.as_ref(),
        SourceSlot::Emissive => group.sources.emissive.as_ref(),
        SourceSlot::Sss => group.sources.sss.as_ref(),
    }
    .map(|source| &source.image)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{
        pipeline::{process_stage1, IntermediateTextures, SourceImage, SourceTextures},
        planar::quantize_u8,
    };

    fn mono(values: Vec<f32>) -> PlanarImage {
        PlanarImage::new(values.len() as u32, 1, vec![values]).unwrap()
    }

    fn rgb(red: Vec<f32>, green: Vec<f32>, blue: Vec<f32>) -> PlanarImage {
        PlanarImage::new(red.len() as u32, 1, vec![red, green, blue]).unwrap()
    }

    fn one_rgb(red: f32, green: f32, blue: f32) -> PlanarImage {
        rgb(vec![red], vec![green], vec![blue])
    }

    fn source(filename: &str, image: PlanarImage) -> SourceImage {
        SourceImage::new(filename, image)
    }

    fn group(sources: SourceTextures) -> TextureGroup {
        TextureGroup {
            base_name: "sample".to_owned(),
            sources,
            intermediate: IntermediateTextures::default(),
            output: OutputTextures::default(),
        }
    }

    fn process_both(group: &mut TextureGroup, settings: &TextureSettings) {
        process_stage1(group, &settings.intermediate_settings()).unwrap();
        process_stage2(group, settings).unwrap();
    }

    fn assert_close(actual: f32, expected: f32) {
        assert!(
            (actual - expected).abs() <= 1.0e-6,
            "{actual} != {expected}"
        );
    }

    fn solid_mono(width: u32, height: u32, value: f32) -> PlanarImage {
        let count = (width * height) as usize;
        PlanarImage::new(width, height, vec![vec![value; count]]).unwrap()
    }

    fn solid_rgb(width: u32, height: u32, r: f32, g: f32, b: f32) -> PlanarImage {
        let count = (width * height) as usize;
        PlanarImage::new(
            width,
            height,
            vec![vec![r; count], vec![g; count], vec![b; count]],
        )
        .unwrap()
    }

    fn mixed_group() -> TextureGroup {
        // basecolor 512, ao 128, normal 256, roughness 128, height 128 — scaled
        // stand-ins for 4K/1K/2K/1K/1K; the ratios exercise every combine path.
        group(SourceTextures {
            diffuse: Some(source("mix_diffuse.png", solid_rgb(512, 512, 0.6, 0.5, 0.4))),
            ao: Some(source("mix_ao.png", solid_mono(128, 128, 0.5))),
            normal: Some(source("mix_normal_dx.png", solid_rgb(256, 256, 0.5, 0.5, 1.0))),
            roughness: Some(source("mix_roughness.png", solid_mono(128, 128, 0.25))),
            height: Some(source("mix_height.png", solid_mono(128, 128, 0.5))),
            ..SourceTextures::default()
        })
    }

    #[test]
    fn t017_anchor1_original_keeps_each_primary_size() {
        let mut group = mixed_group();
        let settings = TextureSettings {
            diff_format: DiffFormat::DiffuseAo,
            process_metallic: false,
            output_resolution: OutputResolution::Original,
            ..TextureSettings::default()
        };
        process_both(&mut group, &settings);

        let diff = group.output.diff.unwrap().image;
        assert_eq!((diff.width, diff.height), (512, 512)); // AO (128) upsampled onto it
        let ddna = group.output.ddna.unwrap().image;
        assert_eq!((ddna.width, ddna.height), (256, 256)); // roughness (128) fitted
        assert_eq!(ddna.channels(), 4);
        let displ = group.output.displ.unwrap().image;
        assert_eq!((displ.width, displ.height), (128, 128));
    }

    #[test]
    fn t017_anchor2_max_caps_but_never_upscales() {
        let mut group = mixed_group();
        let settings = TextureSettings {
            diff_format: DiffFormat::DiffuseAo,
            process_metallic: false,
            output_resolution: OutputResolution::Max(256),
            ..TextureSettings::default()
        };
        process_both(&mut group, &settings);

        let diff = group.output.diff.unwrap().image;
        assert_eq!((diff.width, diff.height), (256, 256)); // 512 capped to 256
        let ddna = group.output.ddna.unwrap().image;
        assert_eq!((ddna.width, ddna.height), (256, 256)); // already at target
        let displ = group.output.displ.unwrap().image;
        assert_eq!((displ.width, displ.height), (128, 128)); // below target, not upscaled
    }

    #[test]
    fn t017_anchor3_aspect_mismatch_ao_hard_scaled_without_crop() {
        // AO 256x128, horizontal gradient dark->bright; base 512x512.
        let (ao_w, ao_h) = (256u32, 128u32);
        let mut ao_plane = Vec::with_capacity((ao_w * ao_h) as usize);
        for _y in 0..ao_h {
            for x in 0..ao_w {
                ao_plane.push(x as f32 / (ao_w as f32 - 1.0));
            }
        }
        let ao = PlanarImage::new(ao_w, ao_h, vec![ao_plane]).unwrap();
        let mut group = group(SourceTextures {
            diffuse: Some(source("mix_diffuse.png", solid_rgb(512, 512, 0.6, 0.6, 0.6))),
            ao: Some(source("mix_ao.png", ao)),
            ..SourceTextures::default()
        });
        let settings = TextureSettings {
            diff_format: DiffFormat::DiffuseAo,
            process_metallic: false,
            output_resolution: OutputResolution::Original,
            ..TextureSettings::default()
        };
        process_both(&mut group, &settings);

        let diff = group.output.diff.unwrap().image;
        assert_eq!((diff.width, diff.height), (512, 512));
        // Gradient must span the full width (non-uniform stretch, not cropped):
        // left column near-black, right column near the un-darkened base.
        let row = 200u32 * 512; // arbitrary interior row
        let left = diff.planes[0][(row) as usize];
        let mid = diff.planes[0][(row + 256) as usize];
        let right = diff.planes[0][(row + 511) as usize];
        assert!(left < mid && mid < right, "AO darkening must vary left->right");
        assert!(left < 0.15, "left edge should be strongly darkened, got {left}");
        assert!(right > 0.55, "right edge should be near base, got {right}");
    }

    #[test]
    fn anchor_one_ddna_alpha_is_exact_inverse_for_all_u8_roughness() {
        let roughness_u8 = (0..=u8::MAX).collect::<Vec<_>>();
        let roughness = PlanarImage::from_interleaved_u8(256, 1, 1, &roughness_u8).unwrap();
        let normal =
            PlanarImage::new(256, 1, vec![vec![0.5; 256], vec![0.5; 256], vec![1.0; 256]]).unwrap();
        let mut group = group(SourceTextures {
            normal: Some(source("sample_normal_dx.png", normal)),
            roughness: Some(source("sample_roughness.png", roughness)),
            ..SourceTextures::default()
        });
        process_both(&mut group, &TextureSettings::default());

        let ddna = group.output.ddna.unwrap();
        assert_eq!(ddna.filename, "sample_ddna.tif");
        let alpha = ddna.image.planes[3]
            .iter()
            .map(|value| quantize_u8(*value))
            .collect::<Vec<_>>();
        let expected = roughness_u8
            .iter()
            .map(|value| u8::MAX - value)
            .collect::<Vec<_>>();
        assert_eq!(alpha, expected);
    }

    #[test]
    fn def09_diff_uses_linear_base_multiply_and_preserves_alpha_mask() {
        let mut group = group(SourceTextures {
            diffuse: Some(source("sample_diffuse.png", one_rgb(0.8, 0.4, 0.1))),
            ao: Some(source("sample_ao.png", mono(vec![0.5]))),
            alpha: Some(source("sample_opacity.png", mono(vec![0.25]))),
            ..SourceTextures::default()
        });
        let settings = TextureSettings {
            diff_format: DiffFormat::DiffuseAo,
            process_metallic: false,
            ..TextureSettings::default()
        };
        process_both(&mut group, &settings);
        let diff = group.output.diff.unwrap().image;

        for (channel, encoded) in [0.8, 0.4, 0.1].into_iter().enumerate() {
            assert_close(
                diff.planes[channel][0],
                srgb_encode(srgb_decode(encoded) * 0.5),
            );
        }
        assert_close(diff.planes[3][0], 0.25);
    }

    #[test]
    fn anchor_three_displacement_has_four_identical_channels() {
        let mut group = group(SourceTextures {
            displacement: Some(source(
                "sample_height.png",
                rgb(vec![1.0, 0.0], vec![0.0, 1.0], vec![0.0, 0.0]),
            )),
            ..SourceTextures::default()
        });
        process_both(&mut group, &TextureSettings::default());
        let displ = group.output.displ.unwrap();
        assert_eq!(displ.filename, "sample_displ.tif");
        assert_eq!(displ.image.channels(), 4);
        for channel in 1..4 {
            assert_eq!(displ.image.planes[channel], displ.image.planes[0]);
        }
    }

    #[test]
    fn anchor_four_selects_ddna_with_gloss_and_ddn_without_it() {
        let normal = one_rgb(0.5, 0.25, 1.0);
        let mut with_gloss = group(SourceTextures {
            normal: Some(source("sample_normal.png", normal.clone())),
            glossiness: Some(source("sample_gloss.png", mono(vec![0.75]))),
            ..SourceTextures::default()
        });
        process_both(&mut with_gloss, &TextureSettings::default());
        assert_eq!(
            with_gloss.output.ddna.as_ref().unwrap().filename,
            "sample_ddna.tif"
        );
        assert_close(with_gloss.output.ddna.unwrap().image.planes[3][0], 0.75);

        let mut without_gloss = group(SourceTextures {
            normal: Some(source("sample_normal.png", normal)),
            ..SourceTextures::default()
        });
        process_both(&mut without_gloss, &TextureSettings::default());
        let ddn = without_gloss.output.ddna.unwrap();
        assert_eq!(ddn.filename, "sample_ddn.tif");
        assert_eq!(ddn.image.channels(), 3);
    }

    #[test]
    fn anchor_five_output_resolution_never_upscales_small_images() {
        let small = PlanarImage::new(
            512,
            1,
            vec![vec![0.25; 512], vec![0.5; 512], vec![0.75; 512]],
        )
        .unwrap();
        let mut group = group(SourceTextures {
            diffuse: Some(source("sample_diffuse.png", small)),
            ..SourceTextures::default()
        });
        let settings = TextureSettings {
            output_resolution: OutputResolution::Max(1024),
            process_metallic: false,
            ..TextureSettings::default()
        };
        process_both(&mut group, &settings);
        let diff = group.output.diff.unwrap().image;
        assert_eq!((diff.width, diff.height), (512, 1));
    }

    #[test]
    fn anchor_six_fallback_defaults_produce_only_spec_for_empty_group() {
        let settings = TextureSettings::default();
        assert!(settings.generate_missing_spec);
        assert!(!settings.generate_missing_emissive);
        assert!(!settings.generate_missing_sss);
        assert!(!settings.generate_sss_from_diffuse);
        assert!(!settings.dither);
        assert_eq!(settings.texture_types, TextureTypeSettings::default());

        let mut group = group(SourceTextures::default());
        process_stage2(&mut group, &settings).unwrap();
        assert!(group.output.diff.is_none());
        assert!(group.output.spec.is_some());
        assert!(group.output.ddna.is_none());
        assert!(group.output.displ.is_none());
        assert!(group.output.emissive.is_none());
        assert!(group.output.sss.is_none());
    }

    #[test]
    fn spec_emissive_and_sss_fallbacks_use_signed_constants_and_ce_suffixes() {
        let diffuse = one_rgb(0.2, 0.5, 0.8);
        let mut group = group(SourceTextures {
            diffuse: Some(source("sample_diffuse.png", diffuse)),
            ..SourceTextures::default()
        });
        let settings = TextureSettings {
            process_metallic: false,
            generate_missing_emissive: true,
            generate_missing_sss: true,
            ..TextureSettings::default()
        };
        process_both(&mut group, &settings);

        let spec = group.output.spec.unwrap();
        assert_eq!(
            spec.image,
            one_rgb(62.0 / 255.0, 62.0 / 255.0, 62.0 / 255.0)
        );
        let emissive = group.output.emissive.unwrap();
        assert_eq!(emissive.filename, "sample_em.tif");
        assert_eq!(emissive.image, one_rgb(0.0, 0.0, 0.0));
        let sss = group.output.sss.unwrap();
        assert_eq!(sss.filename, "sample_sss.tif");
        assert_eq!(sss.image, one_rgb(40.0 / 255.0, 25.0 / 255.0, 25.0 / 255.0));
    }

    #[test]
    fn source_brightness_and_sss_intensity_clamp_without_transfer_functions() {
        let mut group = group(SourceTextures {
            emissive: Some(source("sample_em.png", one_rgb(0.5, 0.25, 0.1))),
            sss: Some(source("sample_sss.png", one_rgb(0.5, 0.25, 0.1))),
            ..SourceTextures::default()
        });
        let settings = TextureSettings {
            emissive_brightness: 10.0,
            sss_intensity: 0.0,
            ..TextureSettings::default()
        };
        process_stage2(&mut group, &settings).unwrap();
        assert_eq!(group.output.emissive.unwrap().image, one_rgb(1.0, 1.0, 0.5));
        let sss = group.output.sss.unwrap().image;
        assert_close(sss.planes[0][0], 0.05);
        assert_close(sss.planes[1][0], 0.025);
        assert_close(sss.planes[2][0], 0.01);
    }

    #[test]
    fn sss_from_diffuse_uses_separate_contrast_setting() {
        let diffuse = rgb(vec![0.0, 1.0], vec![0.0, 1.0], vec![0.0, 1.0]);
        let mut low_contrast = group(SourceTextures {
            diffuse: Some(source("sample_diffuse.png", diffuse.clone())),
            ..SourceTextures::default()
        });
        let mut high_contrast = group(SourceTextures {
            diffuse: Some(source("sample_diffuse.png", diffuse)),
            ..SourceTextures::default()
        });
        let low = TextureSettings {
            process_metallic: false,
            generate_sss_from_diffuse: true,
            sss_intensity: 3.0,
            sss_contrast: 0.5,
            ..TextureSettings::default()
        };
        let high = TextureSettings {
            sss_contrast: 1.5,
            ..low
        };
        process_both(&mut low_contrast, &low);
        process_both(&mut high_contrast, &high);

        assert_ne!(
            low_contrast.output.sss.unwrap().image,
            high_contrast.output.sss.unwrap().image
        );
    }

    #[test]
    fn stage_two_trace_and_dither_stub_are_deterministic() {
        let sources = SourceTextures {
            diffuse: Some(source("sample_diffuse.png", one_rgb(0.2, 0.3, 0.4))),
            ..SourceTextures::default()
        };
        let mut without_dither = group(sources.clone());
        let mut with_dither = group(sources);
        let base = TextureSettings {
            process_metallic: false,
            ..TextureSettings::default()
        };
        process_both(&mut without_dither, &base);
        let report = process_stage2(
            &mut with_dither,
            &TextureSettings {
                dither: true,
                ..base
            },
        )
        .unwrap();

        assert_eq!(
            report.trace,
            vec![
                Stage2Step::Diff,
                Stage2Step::Spec,
                Stage2Step::Ddna,
                Stage2Step::Displ,
                Stage2Step::Emissive,
                Stage2Step::Sss,
            ]
        );
        assert_eq!(without_dither.output, with_dither.output);
    }
}
