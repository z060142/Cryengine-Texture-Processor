use std::{
    collections::BTreeMap,
    fs,
    path::{Path, PathBuf},
    process::ExitCode,
    time::Instant,
};

use clap::{Args, Parser, Subcommand};
use rayon::prelude::*;
use serde_json::Value;
use texproc::{
    decode_image, process_stage1, process_stage2, scan_inputs, write_stage2_outputs, ArmOrder,
    DiffFormat, OutputResolution, OutputTextures, ScanEntry, ScanGroup, ScanResult, SourceImage,
    SourceTextures, SuffixTable, TexprocError, TextureGroup, TextureSettings, TextureTypeSettings,
};

const HELP_AFTER: &str = "EXIT CODES:\n  0  success\n  1  runtime or I/O failure\n  2  CLI/configuration error\n  3  grouping gate failure";

#[derive(Parser)]
#[command(
    version,
    about = "CryEngine texture processor",
    after_help = HELP_AFTER
)]
struct Cli {
    #[command(subcommand)]
    command: Command,
}

#[derive(Subcommand)]
enum Command {
    /// Dry-run deterministic filename/header grouping and emit JSON.
    Scan(ScanArgs),
    /// Group, process Stage 1/2 in parallel, and write TIFF/LZW outputs.
    Process(ProcessArgs),
}

#[derive(Args)]
struct ScanArgs {
    /// JSON suffix table replacing the embedded defaults.
    #[arg(long)]
    suffixes: Option<PathBuf>,
    /// Write grouping JSON here instead of stdout.
    #[arg(long)]
    out: Option<PathBuf>,
    /// Input files or directories (directories are recursive).
    #[arg(required = true)]
    inputs: Vec<PathBuf>,
}

#[derive(Args)]
struct ProcessArgs {
    /// Texture settings JSON (§7 plus arm_order/sss_contrast/dither).
    #[arg(long)]
    settings: Option<PathBuf>,
    /// JSON suffix table replacing the embedded defaults.
    #[arg(long)]
    suffixes: Option<PathBuf>,
    /// Consume a previously reviewed `scan --out` grouping JSON.
    #[arg(long, conflicts_with = "suffixes")]
    groups: Option<PathBuf>,
    /// Output directory for TIFF/LZW textures.
    #[arg(long, required = true)]
    out: PathBuf,
    /// Permit unknown-only groups instead of exiting 3.
    #[arg(long)]
    allow_unknown: bool,
    /// Inputs to scan when --groups is not supplied.
    inputs: Vec<PathBuf>,
}

fn main() -> ExitCode {
    match Cli::parse().command {
        Command::Scan(args) => run_scan(args),
        Command::Process(args) => run_process(args),
    }
}

fn run_scan(args: ScanArgs) -> ExitCode {
    let suffixes = match load_suffixes(args.suffixes.as_deref()) {
        Ok(value) => value,
        Err(error) => return fail(2, error),
    };
    let result = match scan_inputs(&args.inputs, &suffixes) {
        Ok(value) => value,
        Err(error) => return fail(1, error),
    };
    let json = serde_json::to_string_pretty(&result).expect("scan result is serializable");
    if let Some(path) = args.out {
        if let Err(error) = fs::write(&path, format!("{json}\n")) {
            return fail(
                1,
                TexprocError::new(format!("failed to write {}: {error}", path.display())),
            );
        }
    } else {
        println!("{json}");
    }
    ExitCode::SUCCESS
}

fn run_process(args: ProcessArgs) -> ExitCode {
    if args.groups.is_none() && args.inputs.is_empty() {
        return fail(
            2,
            TexprocError::new("process requires INPUTS unless --groups is supplied"),
        );
    }
    if args.groups.is_some() && !args.inputs.is_empty() {
        return fail(
            2,
            TexprocError::new("process does not accept INPUTS when --groups is supplied"),
        );
    }
    let settings = match load_settings(args.settings.as_deref()) {
        Ok(value) => value,
        Err(error) => return fail(2, error),
    };
    let scan = if let Some(path) = args.groups {
        match read_groups(&path) {
            Ok(value) => value,
            Err(error) => return fail(2, error),
        }
    } else {
        let suffixes = match load_suffixes(args.suffixes.as_deref()) {
            Ok(value) => value,
            Err(error) => return fail(2, error),
        };
        match scan_inputs(&args.inputs, &suffixes) {
            Ok(value) => value,
            Err(error) => return fail(1, error),
        }
    };

    let blocked = scan.unknown_only_groups().collect::<Vec<_>>();
    if !args.allow_unknown && !blocked.is_empty() {
        for group in blocked {
            eprintln!(
                "grouping gate: unknown-only group `{}` ({} file(s))",
                group.base_name,
                group.unknown.len()
            );
        }
        return ExitCode::from(3);
    }

    let started = Instant::now();
    let output_root = &args.out;
    let results = scan
        .groups
        .par_iter()
        .map(|group| process_group(group, &settings, output_root))
        .collect::<Vec<_>>();
    for result in results {
        match result {
            Ok((base_name, count, elapsed)) => {
                eprintln!("processed {base_name}: {count} output(s), {elapsed:.3}s");
            }
            Err(error) => return fail(1, error),
        }
    }
    eprintln!(
        "processed {} group(s) in {:.3}s with {} rayon thread(s)",
        scan.groups.len(),
        started.elapsed().as_secs_f64(),
        rayon::current_num_threads()
    );
    ExitCode::SUCCESS
}

fn process_group(
    scan_group: &ScanGroup,
    settings: &TextureSettings,
    output_root: &Path,
) -> texproc::Result<(String, usize, f64)> {
    let started = Instant::now();
    let sources = load_sources(&scan_group.slots, settings)?;
    let mut group = TextureGroup {
        base_name: scan_group.base_name.clone(),
        sources,
        intermediate: Default::default(),
        output: OutputTextures::default(),
    };
    process_stage1(&mut group, &settings.intermediate_settings())?;
    process_stage2(&mut group, settings)?;
    let written = write_stage2_outputs(&group.output, output_root)?;
    Ok((
        scan_group.base_name.clone(),
        written.len(),
        started.elapsed().as_secs_f64(),
    ))
}

fn load_sources(
    slots: &BTreeMap<String, ScanEntry>,
    settings: &TextureSettings,
) -> texproc::Result<SourceTextures> {
    let mut sources = SourceTextures::default();
    for (source_type, entry) in slots {
        if !source_is_required(source_type, settings) {
            continue;
        }
        let source = SourceImage::new(&entry.filename, decode_image(&entry.path)?);
        match source_type.as_str() {
            "diffuse" => sources.diffuse = Some(source),
            "normal" => sources.normal = Some(source),
            "specular" => sources.specular = Some(source),
            "glossiness" => sources.glossiness = Some(source),
            "roughness" => sources.roughness = Some(source),
            "displacement" => sources.displacement = Some(source),
            "metallic" => sources.metallic = Some(source),
            "ao" => sources.ao = Some(source),
            "alpha" => sources.alpha = Some(source),
            "emissive" => sources.emissive = Some(source),
            "sss" => sources.sss = Some(source),
            "arm" => sources.arm = Some(source),
            other => {
                return Err(TexprocError::new(format!(
                    "groups JSON contains unsupported source type `{other}`"
                )));
            }
        }
    }
    Ok(sources)
}

fn source_is_required(source_type: &str, settings: &TextureSettings) -> bool {
    let types = settings.texture_types;
    match source_type {
        "diffuse" => {
            types.diff
                || types.spec
                || (types.emissive && settings.generate_missing_emissive)
                || (types.sss
                    && (settings.generate_sss_from_diffuse || settings.generate_missing_sss))
        }
        "normal" | "glossiness" | "roughness" => types.ddna,
        "specular" | "metallic" => types.spec || types.diff,
        "displacement" => types.displ || types.ddna,
        "ao" | "alpha" => types.diff,
        "emissive" => types.emissive,
        "sss" => types.sss,
        "arm" => types.diff || types.spec || types.ddna,
        _ => false,
    }
}

fn load_suffixes(path: Option<&Path>) -> texproc::Result<SuffixTable> {
    path.map_or_else(SuffixTable::embedded, SuffixTable::load)
}

fn read_groups(path: &Path) -> texproc::Result<ScanResult> {
    let text = fs::read_to_string(path).map_err(|error| {
        TexprocError::new(format!("failed to read groups {}: {error}", path.display()))
    })?;
    serde_json::from_str(&text)
        .map_err(|error| TexprocError::new(format!("invalid groups JSON: {error}")))
}

fn load_settings(path: Option<&Path>) -> texproc::Result<TextureSettings> {
    let Some(path) = path else {
        return Ok(TextureSettings::default());
    };
    let text = fs::read_to_string(path).map_err(|error| {
        TexprocError::new(format!(
            "failed to read settings {}: {error}",
            path.display()
        ))
    })?;
    let value: Value = serde_json::from_str(&text)
        .map_err(|error| TexprocError::new(format!("invalid settings JSON: {error}")))?;
    let object = value
        .as_object()
        .ok_or_else(|| TexprocError::new("settings JSON must be an object"))?;
    let mut settings = TextureSettings::default();
    for (key, value) in object {
        match key.as_str() {
            "output_resolution" => {
                let text = value.as_str().ok_or_else(|| {
                    TexprocError::new("output_resolution must be `original` or a numeric string")
                })?;
                settings.output_resolution = if text.eq_ignore_ascii_case("original") {
                    OutputResolution::Original
                } else {
                    let maximum: u32 = text.parse().map_err(|_| {
                        TexprocError::new(
                            "output_resolution must be `original` or a positive integer",
                        )
                    })?;
                    if maximum == 0 {
                        return Err(TexprocError::new(
                            "output_resolution must be `original` or a positive integer",
                        ));
                    }
                    OutputResolution::Max(maximum)
                };
            }
            "diff_format" => {
                settings.diff_format = match required_string(value, key)?.as_str() {
                    "albedo" => DiffFormat::Albedo,
                    "diffuse_ao" => DiffFormat::DiffuseAo,
                    other => {
                        return Err(TexprocError::new(format!("invalid diff_format `{other}`")))
                    }
                }
            }
            "normal_flip_green" => settings.normal_flip_green = required_bool(value, key)?,
            "normalize_height" => settings.normalize_height = required_bool(value, key)?,
            "process_metallic" => settings.process_metallic = required_bool(value, key)?,
            "normal_from_height_strength" => {
                settings.normal_from_height_strength = required_f32(value, key)?
            }
            "generate_missing_spec" => settings.generate_missing_spec = required_bool(value, key)?,
            "generate_missing_emissive" => {
                settings.generate_missing_emissive = required_bool(value, key)?
            }
            "generate_missing_sss" => settings.generate_missing_sss = required_bool(value, key)?,
            "generate_sss_from_diffuse" => {
                settings.generate_sss_from_diffuse = required_bool(value, key)?
            }
            "emissive_brightness" => settings.emissive_brightness = required_f32(value, key)?,
            "sss_intensity" => settings.sss_intensity = required_f32(value, key)?,
            "sss_contrast" => settings.sss_contrast = required_f32(value, key)?,
            "dither" => settings.dither = required_bool(value, key)?,
            "arm_order" => {
                settings.arm_order = match required_string(value, key)?.to_uppercase().as_str() {
                    "ARM" => ArmOrder::Arm,
                    "ORM" => ArmOrder::Orm,
                    "RMA" => ArmOrder::Rma,
                    other => return Err(TexprocError::new(format!("invalid arm_order `{other}`"))),
                }
            }
            "texture_types" => settings.texture_types = parse_texture_types(value)?,
            other => return Err(TexprocError::new(format!("unknown settings key `{other}`"))),
        }
    }
    Ok(settings)
}

fn parse_texture_types(value: &Value) -> texproc::Result<TextureTypeSettings> {
    let object = value
        .as_object()
        .ok_or_else(|| TexprocError::new("texture_types must be an object"))?;
    let mut settings = TextureTypeSettings::default();
    for (key, value) in object {
        let enabled = required_bool(value, key)?;
        match key.as_str() {
            "diff" => settings.diff = enabled,
            "spec" => settings.spec = enabled,
            "ddna" => settings.ddna = enabled,
            "displ" => settings.displ = enabled,
            "emissive" => settings.emissive = enabled,
            "sss" => settings.sss = enabled,
            other => {
                return Err(TexprocError::new(format!(
                    "unknown texture_types key `{other}`"
                )))
            }
        }
    }
    Ok(settings)
}

fn required_string(value: &Value, key: &str) -> texproc::Result<String> {
    value
        .as_str()
        .map(str::to_owned)
        .ok_or_else(|| TexprocError::new(format!("settings `{key}` must be a string")))
}

fn required_bool(value: &Value, key: &str) -> texproc::Result<bool> {
    value
        .as_bool()
        .ok_or_else(|| TexprocError::new(format!("settings `{key}` must be boolean")))
}

fn required_f32(value: &Value, key: &str) -> texproc::Result<f32> {
    value
        .as_f64()
        .map(|value| value as f32)
        .filter(|value| value.is_finite())
        .ok_or_else(|| TexprocError::new(format!("settings `{key}` must be finite numeric")))
}

fn fail(code: u8, error: impl std::fmt::Display) -> ExitCode {
    eprintln!("error: {error}");
    ExitCode::from(code)
}
