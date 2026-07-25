use std::{
    fs,
    fs::File,
    io::BufReader,
    path::{Path, PathBuf},
    process::Command,
    time::{SystemTime, UNIX_EPOCH},
};

use texproc::ops::{gray, invert};
use texproc::{
    decode_image, probe_header, process_stage1, process_stage2, write_stage2_outputs, DiffFormat,
    IntermediateTextures, OutputResolution, OutputTextures, PlanarImage, SourceImage,
    SourceTextures, TextureGroup, TextureSettings, TextureTypeSettings,
};
use tiff::{
    decoder::{Decoder, DecodingResult},
    ColorType,
};

const BASE_NAME: &str = "KB3D_ENC_AtlasA";
const FIXTURE_FILES: &[&str] = &[
    "KB3D_ENC_AtlasA_ao.png",
    "KB3D_ENC_AtlasA_basecolor.png",
    "KB3D_ENC_AtlasA_height.png",
    "KB3D_ENC_AtlasA_metallic.png",
    "KB3D_ENC_AtlasA_normal.png",
    "KB3D_ENC_AtlasA_opacity.png",
    "KB3D_ENC_AtlasA_roughness.png",
];

#[test]
fn anchor_seven_matches_legacy_python_direct_paths() {
    let Some(context) = ComparisonContext::discover() else {
        eprintln!("T-011 anchor 7 skipped: fixtures, uv, or ImageMagick unavailable");
        return;
    };
    let temp = unique_temp_directory("anchor7");
    let python_output = temp.join("python");
    let rust_output = temp.join("rust");
    fs::create_dir_all(&python_output).unwrap();
    fs::create_dir_all(&rust_output).unwrap();

    run_python(&context, &python_output, DiffFormat::Albedo, false, "all");

    let cases = [
        ("diff", "_diff.tif"),
        ("spec", "_spec.tif"),
        ("ddna", "_ddna.tif"),
        ("displ", "_displ.tif"),
        ("emissive", "_em.tif"),
        ("sss", "_sss.tif"),
    ];
    for (key, suffix) in cases {
        let rust_path = produce_rust_direct_output(&context.fixtures, &rust_output, key);
        let python_path = python_output.join(format!("{BASE_NAME}{suffix}"));
        let max_diff = maximum_pixel_difference(&python_path, &rust_path);
        println!("T011_ANCHOR7 {key} max_diff={max_diff:.9}");
        assert!(
            max_diff <= 1.0 / 255.0 + 1.0e-6,
            "{key} drifted by {max_diff}, above ±1/255"
        );
        fs::remove_file(python_path).unwrap();
        fs::remove_file(rust_path).unwrap();
    }

    fs::remove_dir_all(temp).unwrap();
}

#[test]
fn anchor_two_writes_visual_pairs_when_requested() {
    let Some(output_root) = std::env::var_os("T011_VISUAL_OUTPUT").map(PathBuf::from) else {
        return;
    };
    let context = ComparisonContext::discover()
        .expect("T011_VISUAL_OUTPUT requires fixtures, uv, and ImageMagick");

    let ao_old = output_root.join("ao/old");
    let ao_rust = output_root.join("ao/rust");
    let metallic_old = output_root.join("def05/old");
    let metallic_rust = output_root.join("def05/rust");
    for directory in [&ao_old, &ao_rust, &metallic_old, &metallic_rust] {
        fs::create_dir_all(directory).unwrap();
    }

    let ao_fixtures = output_root.join("input_ao_probe");
    fs::create_dir_all(&ao_fixtures).unwrap();
    for filename in FIXTURE_FILES {
        fs::copy(context.fixtures.join(filename), ao_fixtures.join(filename)).unwrap();
    }
    fs::copy(
        context.fixtures.join("KB3D_ENC_AtlasA_roughness.png"),
        ao_fixtures.join("KB3D_ENC_AtlasA_ao.png"),
    )
    .unwrap();
    let ao_context = ComparisonContext {
        repository: context.repository.clone(),
        fixtures: ao_fixtures,
        driver: context.driver.clone(),
    };
    run_python(&ao_context, &ao_old, DiffFormat::DiffuseAo, false, "diff");
    let ao_rust_path = produce_rust_ao_sample(&ao_context.fixtures, &ao_rust);
    let ao_old_path = ao_old.join(format!("{BASE_NAME}_diff.tif"));
    let ao_diff = maximum_pixel_difference(&ao_old_path, &ao_rust_path);
    assert!(
        ao_diff > 1.0 / 255.0,
        "DEF-09 visual pair unexpectedly remained equivalent"
    );

    let metallic_fixtures = output_root.join("input_metallic_probe");
    fs::create_dir_all(&metallic_fixtures).unwrap();
    for filename in FIXTURE_FILES {
        fs::copy(
            context.fixtures.join(filename),
            metallic_fixtures.join(filename),
        )
        .unwrap();
    }
    fs::copy(
        context.fixtures.join("KB3D_ENC_AtlasA_roughness.png"),
        metallic_fixtures.join("KB3D_ENC_AtlasA_metallic.png"),
    )
    .unwrap();
    let metallic_context = ComparisonContext {
        repository: context.repository.clone(),
        fixtures: metallic_fixtures,
        driver: context.driver.clone(),
    };
    run_python(
        &metallic_context,
        &metallic_old,
        DiffFormat::Albedo,
        true,
        "diff",
    );
    let metallic_rust_path =
        produce_rust_metallic_sample(&metallic_context.fixtures, &metallic_rust);
    let metallic_old_path = metallic_old.join(format!("{BASE_NAME}_diff.tif"));
    let metallic_diff = maximum_pixel_difference(&metallic_old_path, &metallic_rust_path);
    assert!(
        metallic_diff > 1.0 / 255.0,
        "DEF-05 visual pair unexpectedly remained equivalent"
    );

    println!(
        "T011_ANCHOR2 ao_max_diff={ao_diff:.9} def05_max_diff={metallic_diff:.9} root={}",
        output_root.display()
    );
}

struct ComparisonContext {
    repository: PathBuf,
    fixtures: PathBuf,
    driver: PathBuf,
}

impl ComparisonContext {
    fn discover() -> Option<Self> {
        let manifest = Path::new(env!("CARGO_MANIFEST_DIR"));
        let repository = manifest.parent()?.parent()?.to_path_buf();
        let fixtures = repository.join("rebuild/fixtures/textures");
        let driver = repository.join("tools/run_t011_python_baseline.py");
        let fixtures_exist = FIXTURE_FILES
            .iter()
            .all(|filename| fixtures.join(filename).is_file());
        if !fixtures_exist
            || !driver.is_file()
            || !command_succeeds("uv", &["--version"])
            || !command_succeeds("magick", &["-version"])
        {
            return None;
        }
        Some(Self {
            repository,
            fixtures,
            driver,
        })
    }
}

fn command_succeeds(program: &str, arguments: &[&str]) -> bool {
    Command::new(program)
        .args(arguments)
        .output()
        .is_ok_and(|output| output.status.success())
}

fn run_python(
    context: &ComparisonContext,
    output: &Path,
    diff_format: DiffFormat,
    process_metallic: bool,
    outputs: &str,
) {
    let mut command = Command::new("uv");
    command
        .current_dir(&context.repository)
        .args(["run", "python"])
        .arg(&context.driver)
        .arg("--fixtures")
        .arg(&context.fixtures)
        .arg("--output")
        .arg(output)
        .arg("--diff-format")
        .arg(match diff_format {
            DiffFormat::Albedo => "albedo",
            DiffFormat::DiffuseAo => "diffuse_ao",
        })
        .arg("--outputs")
        .arg(outputs);
    if process_metallic {
        command.arg("--process-metallic");
    }
    let result = command.output().expect("legacy Python driver must start");
    assert!(
        result.status.success(),
        "legacy Python driver failed\nstdout:\n{}\nstderr:\n{}",
        String::from_utf8_lossy(&result.stdout),
        String::from_utf8_lossy(&result.stderr)
    );
}

fn produce_rust_direct_output(fixtures: &Path, output: &Path, key: &str) -> PathBuf {
    let mut group = empty_group();
    match key {
        "diff" => {
            group.intermediate.albedo = Some(load(fixtures, "KB3D_ENC_AtlasA_basecolor.png"));
            group.sources.alpha = Some(source(fixtures, "KB3D_ENC_AtlasA_opacity.png"));
        }
        "spec" => {
            let header = probe_header(fixtures.join("KB3D_ENC_AtlasA_basecolor.png")).unwrap();
            let count =
                usize::try_from(u64::from(header.width) * u64::from(header.height)).unwrap();
            group.intermediate.albedo = Some(
                PlanarImage::new(header.width, header.height, vec![vec![0.0; count]]).unwrap(),
            );
        }
        "ddna" => {
            group.intermediate.normal = Some(load(fixtures, "KB3D_ENC_AtlasA_normal.png"));
            group.intermediate.glossiness = Some(invert(&gray(&load(
                fixtures,
                "KB3D_ENC_AtlasA_roughness.png",
            ))));
        }
        "displ" => {
            group.intermediate.height = Some(gray(&load(fixtures, "KB3D_ENC_AtlasA_height.png")));
        }
        "emissive" => {
            group.sources.emissive = Some(source(fixtures, "KB3D_ENC_AtlasA_basecolor.png"));
        }
        "sss" => {
            group.sources.sss = Some(source(fixtures, "KB3D_ENC_AtlasA_basecolor.png"));
        }
        _ => panic!("unknown direct output key {key}"),
    }

    let settings = settings_for_only(key);
    process_stage2(&mut group, &settings).unwrap();
    let written = write_stage2_outputs(&group.output, output).unwrap();
    assert_eq!(written.len(), 1);
    written.into_iter().next().unwrap()
}

fn produce_rust_ao_sample(fixtures: &Path, output: &Path) -> PathBuf {
    let mut group = empty_group();
    group.intermediate.albedo = Some(load(fixtures, "KB3D_ENC_AtlasA_basecolor.png"));
    group.intermediate.ao = Some(gray(&load(fixtures, "KB3D_ENC_AtlasA_ao.png")));
    group.sources.alpha = Some(source(fixtures, "KB3D_ENC_AtlasA_opacity.png"));
    let settings = TextureSettings {
        diff_format: DiffFormat::DiffuseAo,
        texture_types: only_diff(),
        ..TextureSettings::default()
    };
    process_stage2(&mut group, &settings).unwrap();
    write_stage2_outputs(&group.output, output)
        .unwrap()
        .remove(0)
}

fn produce_rust_metallic_sample(fixtures: &Path, output: &Path) -> PathBuf {
    let mut group = empty_group();
    group.sources.diffuse = Some(source(fixtures, "KB3D_ENC_AtlasA_basecolor.png"));
    group.sources.metallic = Some(source(fixtures, "KB3D_ENC_AtlasA_metallic.png"));
    group.sources.alpha = Some(source(fixtures, "KB3D_ENC_AtlasA_opacity.png"));
    let settings = TextureSettings {
        texture_types: only_diff(),
        ..TextureSettings::default()
    };
    process_stage1(&mut group, &settings.intermediate_settings()).unwrap();
    process_stage2(&mut group, &settings).unwrap();
    write_stage2_outputs(&group.output, output)
        .unwrap()
        .remove(0)
}

fn settings_for_only(key: &str) -> TextureSettings {
    let mut texture_types = TextureTypeSettings {
        diff: false,
        spec: false,
        ddna: false,
        displ: false,
        emissive: false,
        sss: false,
    };
    match key {
        "diff" => texture_types.diff = true,
        "spec" => texture_types.spec = true,
        "ddna" => texture_types.ddna = true,
        "displ" => texture_types.displ = true,
        "emissive" => texture_types.emissive = true,
        "sss" => texture_types.sss = true,
        _ => panic!("unknown output key {key}"),
    }
    TextureSettings {
        output_resolution: OutputResolution::Original,
        process_metallic: false,
        texture_types,
        ..TextureSettings::default()
    }
}

fn only_diff() -> TextureTypeSettings {
    TextureTypeSettings {
        diff: true,
        spec: false,
        ddna: false,
        displ: false,
        emissive: false,
        sss: false,
    }
}

fn empty_group() -> TextureGroup {
    TextureGroup {
        base_name: BASE_NAME.to_owned(),
        sources: SourceTextures::default(),
        intermediate: IntermediateTextures::default(),
        output: OutputTextures::default(),
    }
}

fn source(fixtures: &Path, filename: &str) -> SourceImage {
    SourceImage::new(filename, load(fixtures, filename))
}

fn load(fixtures: &Path, filename: &str) -> PlanarImage {
    decode_image(fixtures.join(filename)).unwrap()
}

fn maximum_pixel_difference(first: &Path, second: &Path) -> f32 {
    let first = decode_comparison_image(first);
    let second = decode_image(second).unwrap();
    assert_eq!(
        (first.width, first.height, first.channels()),
        (second.width, second.height, second.channels())
    );
    first
        .planes
        .iter()
        .zip(&second.planes)
        .flat_map(|(first, second)| first.iter().zip(second))
        .map(|(first, second)| (first - second).abs())
        .fold(0.0, f32::max)
}

fn decode_comparison_image(path: &Path) -> PlanarImage {
    if let Ok(image) = decode_image(path) {
        return image;
    }

    let mut decoder = Decoder::new(BufReader::new(File::open(path).unwrap())).unwrap();
    let (width, height) = decoder.dimensions().unwrap();
    assert!(
        matches!(
            decoder.colortype().unwrap(),
            ColorType::GrayA(8)
                | ColorType::Multiband {
                    bit_depth: 8,
                    num_samples: 2
                }
        ),
        "only the legacy DEF-11 two-channel displacement is canonicalized"
    );
    let DecodingResult::U8(samples) = decoder.read_image().unwrap() else {
        panic!("legacy GrayA comparison image must be 8-bit");
    };
    let gray_alpha = PlanarImage::from_interleaved_u8(width, height, 2, &samples).unwrap();
    let gray = gray_alpha.planes[0].clone();
    PlanarImage::new(
        width,
        height,
        vec![
            gray.clone(),
            gray.clone(),
            gray,
            gray_alpha.planes[1].clone(),
        ],
    )
    .unwrap()
}

fn unique_temp_directory(label: &str) -> PathBuf {
    let nonce = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_nanos();
    std::env::temp_dir().join(format!(
        "texproc-t011-{label}-{}-{nonce}",
        std::process::id()
    ))
}
