use std::{
    fs,
    path::{Path, PathBuf},
    process::ExitCode,
    sync::atomic::AtomicBool,
};

use clap::{Args, Parser, Subcommand};
use texproc::{
    load_texture_settings, process_scan_parallel, scan_inputs, ScanResult, SuffixTable,
    TexprocError, TextureSettings,
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
    let settings = match args
        .settings
        .as_deref()
        .map_or_else(|| Ok(TextureSettings::default()), load_texture_settings)
    {
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

    let output_root = &args.out;
    let cancel = AtomicBool::new(false);
    let report = match process_scan_parallel(&scan, &settings, output_root, &cancel, |_| {}) {
        Ok(report) => report,
        Err(error) => return fail(1, error),
    };
    for group in &report.groups {
        eprintln!(
            "processed {}: {} output(s), {:.3}s",
            group.base_name,
            group.written.len(),
            group.elapsed_seconds
        );
    }
    eprintln!(
        "processed {} group(s) in {:.3}s with {} rayon thread(s)",
        report.groups.len(),
        report.elapsed_seconds,
        report.rayon_threads
    );
    ExitCode::SUCCESS
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

fn fail(code: u8, error: impl std::fmt::Display) -> ExitCode {
    eprintln!("error: {error}");
    ExitCode::from(code)
}
