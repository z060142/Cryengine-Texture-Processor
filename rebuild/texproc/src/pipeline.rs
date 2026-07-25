use crate::{
    constants::DEFAULT_NONMETAL_REFLECTION,
    error::{Result, TexprocError},
    ops::{flip_green, gray, invert, linear_burn, normal_from_height, srgb_decode, srgb_encode},
    planar::PlanarImage,
};

#[derive(Clone, Debug, PartialEq)]
pub struct SourceImage {
    pub filename: String,
    pub image: PlanarImage,
}

impl SourceImage {
    pub fn new(filename: impl Into<String>, image: PlanarImage) -> Self {
        Self {
            filename: filename.into(),
            image,
        }
    }
}

#[derive(Clone, Debug, Default, PartialEq)]
pub struct SourceTextures {
    pub diffuse: Option<SourceImage>,
    pub albedo: Option<SourceImage>,
    pub normal: Option<SourceImage>,
    pub specular: Option<SourceImage>,
    pub glossiness: Option<SourceImage>,
    pub roughness: Option<SourceImage>,
    pub displacement: Option<SourceImage>,
    pub height: Option<SourceImage>,
    pub metallic: Option<SourceImage>,
    pub ao: Option<SourceImage>,
    pub alpha: Option<SourceImage>,
    pub emissive: Option<SourceImage>,
    pub sss: Option<SourceImage>,
    pub arm: Option<SourceImage>,
    pub unknown: Vec<SourceImage>,
}

#[derive(Clone, Debug, Default, PartialEq)]
pub struct IntermediateTextures {
    pub albedo: Option<PlanarImage>,
    pub reflection: Option<PlanarImage>,
    pub normal: Option<PlanarImage>,
    pub glossiness: Option<PlanarImage>,
    pub height: Option<PlanarImage>,
    pub ao: Option<PlanarImage>,
    pub roughness: Option<PlanarImage>,
    pub metallic: Option<PlanarImage>,
}

#[derive(Clone, Debug, Default, PartialEq)]
pub struct TextureGroup {
    pub base_name: String,
    pub sources: SourceTextures,
    pub intermediate: IntermediateTextures,
}

#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub enum ArmOrder {
    #[default]
    Arm,
    Orm,
    Rma,
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct IntermediateSettings {
    pub process_metallic: bool,
    pub normal_from_height_strength: f32,
    pub arm_order: ArmOrder,
}

impl Default for IntermediateSettings {
    fn default() -> Self {
        Self {
            process_metallic: true,
            normal_from_height_strength: 10.0,
            arm_order: ArmOrder::Arm,
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Stage1Step {
    Arm,
    Albedo,
    Normal,
    Gloss,
    Reflection,
    Height,
    Ao,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Stage1Diagnostic {
    pub code: &'static str,
    pub message: String,
}

#[derive(Clone, Debug, Default, Eq, PartialEq)]
pub struct Stage1Report {
    pub trace: Vec<Stage1Step>,
    pub diagnostics: Vec<Stage1Diagnostic>,
    pub reflection_glossiness_seen: bool,
}

pub fn process_stage1(
    group: &mut TextureGroup,
    settings: &IntermediateSettings,
) -> Result<Stage1Report> {
    if !settings.normal_from_height_strength.is_finite() {
        return Err(TexprocError::new(
            "normal_from_height_strength must be finite",
        ));
    }

    let mut intermediate = group.intermediate.clone();
    let mut report = Stage1Report::default();

    report.trace.push(Stage1Step::Arm);
    process_arm(&group.sources, &mut intermediate, settings, &mut report)?;

    report.trace.push(Stage1Step::Albedo);
    intermediate.albedo = process_albedo(&group.sources, &intermediate, settings)?;

    report.trace.push(Stage1Step::Normal);
    intermediate.normal = process_normal(&group.sources, settings)?;

    report.trace.push(Stage1Step::Gloss);
    intermediate.glossiness = process_gloss(&group.sources, &intermediate);

    report.trace.push(Stage1Step::Reflection);
    intermediate.reflection =
        process_reflection(&group.sources, &intermediate, settings, &mut report)?;

    report.trace.push(Stage1Step::Height);
    intermediate.height = process_height(&group.sources);

    report.trace.push(Stage1Step::Ao);
    process_ao(&group.sources, &mut intermediate);

    group.intermediate = intermediate;
    Ok(report)
}

fn process_arm(
    sources: &SourceTextures,
    intermediate: &mut IntermediateTextures,
    settings: &IntermediateSettings,
    report: &mut Stage1Report,
) -> Result<()> {
    let Some(source) = &sources.arm else {
        return Ok(());
    };
    if source.image.channels() < 3 {
        return Err(TexprocError::new(format!(
            "INT-ARM requires at least three channels, got {}",
            source.image.channels()
        )));
    }

    let order = arm_order_from_filename(&source.filename, settings.arm_order, report);
    let channel = |index: usize| {
        PlanarImage::new(
            source.image.width,
            source.image.height,
            vec![source.image.planes[index].clone()],
        )
        .expect("extracting one validated plane preserves image validity")
    };

    match order {
        ArmOrder::Arm | ArmOrder::Orm => {
            intermediate.ao = Some(channel(0));
            intermediate.roughness = Some(channel(1));
            intermediate.metallic = Some(channel(2));
        }
        ArmOrder::Rma => {
            intermediate.roughness = Some(channel(0));
            intermediate.metallic = Some(channel(1));
            intermediate.ao = Some(channel(2));
        }
    }
    Ok(())
}

fn arm_order_from_filename(
    filename: &str,
    fallback: ArmOrder,
    report: &mut Stage1Report,
) -> ArmOrder {
    let stem = terminal_stem(filename);
    if has_terminal_token(&stem, "arm") {
        ArmOrder::Arm
    } else if has_terminal_token(&stem, "orm") {
        ArmOrder::Orm
    } else if has_terminal_token(&stem, "rma") {
        ArmOrder::Rma
    } else if has_terminal_token(&stem, "rm") || has_terminal_token(&stem, "ra") {
        report.diagnostics.push(Stage1Diagnostic {
            code: "AMBIGUOUS_ARM_ALIAS",
            message: format!(
                "ambiguous ARM alias in `{filename}`; using configured order {fallback:?}"
            ),
        });
        fallback
    } else {
        fallback
    }
}

fn terminal_stem(filename: &str) -> String {
    let basename = filename
        .rsplit(['/', '\\'])
        .next()
        .unwrap_or(filename)
        .to_ascii_lowercase();
    let mut stem = basename
        .rsplit_once('.')
        .map_or(basename.as_str(), |(value, _)| value)
        .to_owned();
    if let Some((prefix, token)) = stem.rsplit_once(['_', '-']) {
        if is_resolution_token(token) {
            stem = prefix.to_owned();
        }
    }
    stem
}

fn is_resolution_token(token: &str) -> bool {
    let Some(number) = token.strip_suffix('k') else {
        return false;
    };
    !number.is_empty() && number.bytes().all(|byte| byte.is_ascii_digit())
}

fn has_terminal_token(stem: &str, token: &str) -> bool {
    stem == token
        || stem
            .strip_suffix(token)
            .is_some_and(|prefix| prefix.ends_with('_') || prefix.ends_with('-'))
}

fn process_albedo(
    sources: &SourceTextures,
    intermediate: &IntermediateTextures,
    settings: &IntermediateSettings,
) -> Result<Option<PlanarImage>> {
    if let Some(albedo) = &sources.albedo {
        return Ok(Some(albedo.image.clone()));
    }

    let Some(diffuse) = &sources.diffuse else {
        return Ok(None);
    };
    if settings.process_metallic {
        let metallic = sources
            .metallic
            .as_ref()
            .map(|source| &source.image)
            .or(intermediate.metallic.as_ref());
        if let Some(metallic) = metallic {
            let inverted_metallic = invert(&gray(metallic));
            return linear_burn(&diffuse.image, &inverted_metallic).map(Some);
        }
    }
    Ok(Some(diffuse.image.clone()))
}

fn process_normal(
    sources: &SourceTextures,
    settings: &IntermediateSettings,
) -> Result<Option<PlanarImage>> {
    if let Some(normal) = &sources.normal {
        return if normal_convention(&normal.filename) == NormalConvention::OpenGl {
            flip_green(&normal.image).map(Some)
        } else {
            Ok(Some(normal.image.clone()))
        };
    }

    sources
        .displacement
        .as_ref()
        .or(sources.height.as_ref())
        .map(|height| normal_from_height(&height.image, settings.normal_from_height_strength))
        .transpose()
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum NormalConvention {
    DirectX,
    OpenGl,
}

fn normal_convention(filename: &str) -> NormalConvention {
    let filename = filename.to_ascii_lowercase();
    let direct_x_patterns = [
        "_normaldirectx",
        "_normal-directx",
        "_normal_directx",
        "_normaldx",
        "_normal-dx",
        "_normal_dx",
        "_directxnormal",
        "_directx-normal",
        "_directx_normal",
        "_dxnormal",
        "_dx-normal",
        "_dx_normal",
    ];
    if direct_x_patterns
        .iter()
        .any(|pattern| filename.contains(pattern))
    {
        return NormalConvention::DirectX;
    }

    let open_gl_patterns = [
        "_normalopengl",
        "_normal-opengl",
        "_normal_opengl",
        "_normalgl",
        "_normal-gl",
        "_normal_gl",
        "_openglnormal",
        "_opengl-normal",
        "_opengl_normal",
        "_glnormal",
        "_gl-normal",
        "_gl_normal",
    ];
    if open_gl_patterns
        .iter()
        .any(|pattern| filename.contains(pattern))
    {
        NormalConvention::OpenGl
    } else {
        NormalConvention::DirectX
    }
}

fn process_gloss(
    sources: &SourceTextures,
    intermediate: &IntermediateTextures,
) -> Option<PlanarImage> {
    if let Some(source) = &sources.glossiness {
        Some(gray(&source.image))
    } else if let Some(existing) = &intermediate.glossiness {
        Some(gray(existing))
    } else if let Some(roughness) = &intermediate.roughness {
        Some(invert(&gray(roughness)))
    } else {
        sources
            .roughness
            .as_ref()
            .map(|roughness| invert(&gray(&roughness.image)))
    }
}

fn process_reflection(
    sources: &SourceTextures,
    intermediate: &IntermediateTextures,
    settings: &IntermediateSettings,
    report: &mut Stage1Report,
) -> Result<Option<PlanarImage>> {
    if let Some(specular) = &sources.specular {
        report.reflection_glossiness_seen = intermediate.glossiness.is_some();
        return Ok(Some(specular.image.clone()));
    }
    if !settings.process_metallic {
        return Ok(None);
    }

    let Some(diffuse) = &sources.diffuse else {
        return Ok(None);
    };
    let metallic = sources
        .metallic
        .as_ref()
        .map(|source| &source.image)
        .or(intermediate.metallic.as_ref());

    metallic
        .map(|metallic| metal_reflection(&diffuse.image, metallic))
        .transpose()
}

fn metal_reflection(diffuse: &PlanarImage, metallic: &PlanarImage) -> Result<PlanarImage> {
    if diffuse.width != metallic.width || diffuse.height != metallic.height {
        return Err(TexprocError::new(format!(
            "INT-REFLECTION dimension mismatch: diffuse {}x{} versus metallic {}x{}",
            diffuse.width, diffuse.height, metallic.width, metallic.height
        )));
    }

    let metallic = gray(metallic);
    let gray_linear = srgb_decode(DEFAULT_NONMETAL_REFLECTION[0]);
    let mut planes = vec![
        Vec::with_capacity(diffuse.pixel_count()),
        Vec::with_capacity(diffuse.pixel_count()),
        Vec::with_capacity(diffuse.pixel_count()),
    ];
    for index in 0..diffuse.pixel_count() {
        let factor = metallic.planes[0][index];
        for (channel, plane) in planes.iter_mut().enumerate() {
            let diffuse_encoded = if diffuse.channels() < 3 {
                diffuse.planes[0][index]
            } else {
                diffuse.planes[channel][index]
            };
            let diffuse_linear = srgb_decode(diffuse_encoded);
            plane.push(srgb_encode(
                gray_linear + (diffuse_linear - gray_linear) * factor,
            ));
        }
    }
    PlanarImage::new(diffuse.width, diffuse.height, planes)
}

fn process_height(sources: &SourceTextures) -> Option<PlanarImage> {
    sources
        .displacement
        .as_ref()
        .or(sources.height.as_ref())
        .map(|height| gray(&height.image))
}

fn process_ao(sources: &SourceTextures, intermediate: &mut IntermediateTextures) {
    if intermediate.ao.is_none() {
        intermediate.ao = sources.ao.as_ref().map(|ao| gray(&ao.image));
    }
}

#[cfg(test)]
mod tests {
    use std::{
        fs,
        sync::atomic::{AtomicU64, Ordering},
    };

    use super::*;
    use crate::planar::quantize_u8;

    static TEMP_SEQUENCE: AtomicU64 = AtomicU64::new(0);

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

    fn run(sources: SourceTextures) -> (TextureGroup, Stage1Report) {
        let mut group = TextureGroup {
            base_name: "sample".to_owned(),
            sources,
            intermediate: IntermediateTextures::default(),
        };
        let report = process_stage1(&mut group, &IntermediateSettings::default()).unwrap();
        (group, report)
    }

    fn assert_close(actual: f32, expected: f32) {
        assert!(
            (actual - expected).abs() <= 1.0e-6,
            "{actual} != {expected}"
        );
    }

    #[test]
    fn anchor_one_roughness_quantizes_to_exact_u8_inverse_for_all_values() {
        let roughness_u8 = (0..=u8::MAX).collect::<Vec<_>>();
        let roughness = PlanarImage::from_interleaved_u8(256, 1, 1, &roughness_u8).unwrap();
        let (group, _) = run(SourceTextures {
            roughness: Some(source("surface_roughness.png", roughness)),
            ..SourceTextures::default()
        });

        let actual = group.intermediate.glossiness.unwrap().to_interleaved_u8();
        let expected = roughness_u8
            .iter()
            .map(|value| u8::MAX - value)
            .collect::<Vec<_>>();
        assert_eq!(actual, expected);
    }

    #[test]
    fn def08_reflection_uses_decoded_gray62_and_linear_lerp() {
        let diffuse = one_rgb(0.8, 0.4, 0.1);
        let metallic = mono(vec![0.0, 1.0, 0.5]);
        let diffuse = PlanarImage::new(
            3,
            1,
            vec![
                vec![diffuse.planes[0][0]; 3],
                vec![diffuse.planes[1][0]; 3],
                vec![diffuse.planes[2][0]; 3],
            ],
        )
        .unwrap();
        let (group, _) = run(SourceTextures {
            diffuse: Some(source("surface_diffuse.png", diffuse.clone())),
            metallic: Some(source("surface_metallic.png", metallic)),
            ..SourceTextures::default()
        });
        let reflection = group.intermediate.reflection.unwrap();

        for plane in &reflection.planes {
            assert_eq!(quantize_u8(plane[0]), 62);
        }
        for (channel, gray_encoded) in DEFAULT_NONMETAL_REFLECTION.iter().enumerate() {
            assert_close(reflection.planes[channel][1], diffuse.planes[channel][1]);
            let expected = srgb_encode(
                srgb_decode(*gray_encoded)
                    + (srgb_decode(diffuse.planes[channel][2]) - srgb_decode(*gray_encoded)) * 0.5,
            );
            assert_close(reflection.planes[channel][2], expected);

            let encoded_lerp = *gray_encoded + (diffuse.planes[channel][2] - *gray_encoded) * 0.5;
            assert!((reflection.planes[channel][2] - encoded_lerp).abs() > 1.0e-3);
        }
    }

    #[test]
    fn def05_albedo_priority_is_dedicated_then_metallic_burn_then_naked_diffuse() {
        let diffuse = one_rgb(0.8, 0.4, 0.1);
        let metallic = mono(vec![0.25]);
        let dedicated = one_rgb(0.2, 0.3, 0.4);

        let (dedicated_group, _) = run(SourceTextures {
            diffuse: Some(source("surface_diffuse.png", diffuse.clone())),
            metallic: Some(source("surface_metallic.png", metallic.clone())),
            albedo: Some(source("surface_albedo.png", dedicated.clone())),
            ..SourceTextures::default()
        });
        assert_eq!(dedicated_group.intermediate.albedo, Some(dedicated));

        let (burn_group, _) = run(SourceTextures {
            diffuse: Some(source("surface_diffuse.png", diffuse.clone())),
            metallic: Some(source("surface_metallic.png", metallic)),
            ..SourceTextures::default()
        });
        let burned = burn_group.intermediate.albedo.unwrap();
        assert_close(burned.planes[0][0], 0.55);
        assert_close(burned.planes[1][0], 0.15);
        assert_close(burned.planes[2][0], 0.0);

        let (naked_group, _) = run(SourceTextures {
            diffuse: Some(source("surface_diffuse.png", diffuse.clone())),
            ..SourceTextures::default()
        });
        assert_eq!(naked_group.intermediate.albedo, Some(diffuse));
    }

    #[test]
    fn def03_gloss_executes_before_specular_reflection() {
        let (group, report) = run(SourceTextures {
            specular: Some(source("surface_specular.png", one_rgb(0.2, 0.3, 0.4))),
            roughness: Some(source("surface_roughness.png", mono(vec![0.75]))),
            ..SourceTextures::default()
        });

        assert_eq!(
            report.trace,
            vec![
                Stage1Step::Arm,
                Stage1Step::Albedo,
                Stage1Step::Normal,
                Stage1Step::Gloss,
                Stage1Step::Reflection,
                Stage1Step::Height,
                Stage1Step::Ao,
            ]
        );
        assert!(report.reflection_glossiness_seen);
        assert_eq!(group.intermediate.glossiness.unwrap().planes[0], vec![0.25]);
        assert_eq!(group.intermediate.reflection, Some(one_rgb(0.2, 0.3, 0.4)));
    }

    #[test]
    fn arm_order_supports_arm_orm_and_rma_layouts() {
        let packed = one_rgb(0.1, 0.2, 0.3);
        for (order, expected) in [
            (ArmOrder::Arm, (0.1, 0.2, 0.3)),
            (ArmOrder::Orm, (0.1, 0.2, 0.3)),
            (ArmOrder::Rma, (0.3, 0.1, 0.2)),
        ] {
            let mut group = TextureGroup {
                sources: SourceTextures {
                    arm: Some(source("surface_packed.png", packed.clone())),
                    ..SourceTextures::default()
                },
                ..TextureGroup::default()
            };
            process_stage1(
                &mut group,
                &IntermediateSettings {
                    arm_order: order,
                    ..IntermediateSettings::default()
                },
            )
            .unwrap();
            assert_close(
                group.intermediate.ao.as_ref().unwrap().planes[0][0],
                expected.0,
            );
            assert_close(
                group.intermediate.roughness.as_ref().unwrap().planes[0][0],
                expected.1,
            );
            assert_close(
                group.intermediate.metallic.as_ref().unwrap().planes[0][0],
                expected.2,
            );
        }
    }

    #[test]
    fn explicit_arm_alias_overrides_setting_and_ambiguous_alias_reports() {
        let packed = one_rgb(0.1, 0.2, 0.3);
        let mut aliased = TextureGroup {
            sources: SourceTextures {
                arm: Some(source("surface_rma_4k.png", packed.clone())),
                ..SourceTextures::default()
            },
            ..TextureGroup::default()
        };
        process_stage1(
            &mut aliased,
            &IntermediateSettings {
                arm_order: ArmOrder::Arm,
                ..IntermediateSettings::default()
            },
        )
        .unwrap();
        assert_eq!(aliased.intermediate.ao.unwrap().planes[0], packed.planes[2]);

        let mut ambiguous = TextureGroup {
            sources: SourceTextures {
                arm: Some(source("surface_rm.png", packed)),
                ..SourceTextures::default()
            },
            ..TextureGroup::default()
        };
        let report = process_stage1(
            &mut ambiguous,
            &IntermediateSettings {
                arm_order: ArmOrder::Rma,
                ..IntermediateSettings::default()
            },
        )
        .unwrap();
        assert_eq!(report.diagnostics.len(), 1);
        assert_eq!(report.diagnostics[0].code, "AMBIGUOUS_ARM_ALIAS");
        assert_eq!(ambiguous.intermediate.ao.unwrap().planes[0], vec![0.3]);
    }

    #[test]
    fn normal_filename_boundary_recognizes_gl_and_defaults_false_positives_to_dx() {
        let normal = one_rgb(0.5, 0.2, 1.0);
        for filename in [
            "stone_normal_gl.png",
            "stone_normal-opengl.tif",
            "stone_gl_normal.exr",
        ] {
            let (group, _) = run(SourceTextures {
                normal: Some(source(filename, normal.clone())),
                ..SourceTextures::default()
            });
            assert_close(group.intermediate.normal.unwrap().planes[1][0], 0.8);
        }

        for filename in [
            "stone_normal_dx.png",
            "stone_directx_normal.tif",
            "glass_normal.png",
            "single_nrm.png",
            "shingle_n.png",
        ] {
            let (group, _) = run(SourceTextures {
                normal: Some(source(filename, normal.clone())),
                ..SourceTextures::default()
            });
            assert_close(group.intermediate.normal.unwrap().planes[1][0], 0.2);
        }
    }

    #[test]
    fn normal_height_ao_and_unknown_slots_are_in_memory_products() {
        let (group, _) = run(SourceTextures {
            height: Some(source("surface_height.png", mono(vec![0.0, 0.5, 1.0]))),
            ao: Some(source(
                "surface_ao.png",
                rgb(vec![1.0], vec![0.0], vec![0.0]),
            )),
            unknown: vec![source("surface_custom.png", mono(vec![0.5]))],
            ..SourceTextures::default()
        });

        assert_eq!(group.intermediate.normal.unwrap().channels(), 3);
        assert_eq!(
            group.intermediate.height.unwrap().planes[0],
            vec![0.0, 0.5, 1.0]
        );
        assert_close(group.intermediate.ao.unwrap().planes[0][0], 0.299);
        assert_eq!(group.sources.unknown.len(), 1);
    }

    #[test]
    fn stage_one_does_not_write_to_temp_directory() {
        let sequence = TEMP_SEQUENCE.fetch_add(1, Ordering::Relaxed);
        let temp_dir =
            std::env::temp_dir().join(format!("texproc-t010-{}-{sequence}", std::process::id()));
        fs::create_dir(&temp_dir).unwrap();
        let path = |name: &str| temp_dir.join(name).to_string_lossy().into_owned();

        let (_group, _report) = run(SourceTextures {
            diffuse: Some(source(&path("surface_diffuse.png"), one_rgb(0.8, 0.4, 0.1))),
            metallic: Some(source(&path("surface_metallic.png"), mono(vec![0.5]))),
            roughness: Some(source(&path("surface_roughness.png"), mono(vec![0.25]))),
            normal: Some(source(
                &path("surface_normal_gl.png"),
                one_rgb(0.5, 0.25, 1.0),
            )),
            displacement: Some(source(&path("surface_displ.png"), mono(vec![0.5]))),
            ao: Some(source(&path("surface_ao.png"), mono(vec![0.75]))),
            ..SourceTextures::default()
        });

        assert_eq!(fs::read_dir(&temp_dir).unwrap().count(), 0);
        fs::remove_dir(&temp_dir).unwrap();
    }
}
