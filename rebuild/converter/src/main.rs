use clap::{Parser, Subcommand};
use std::path::PathBuf;
use std::process::ExitCode;

#[derive(Parser)]
#[command(
    version,
    about = "CryEngine FBX converter",
    after_help = "EXIT CODES:\n  0  Success\n  1  Other operational error\n  2  Invalid arguments or input\n  3  Request schema gate failed"
)]
struct Cli {
    #[command(subcommand)]
    command: Command,
}

#[derive(Subcommand)]
enum Command {
    /// Dump raw ufbx scene evidence without applying conversion policy.
    Dump {
        /// Source FBX file.
        input: PathBuf,
        /// Destination JSON report.
        #[arg(long)]
        out: PathBuf,
    },
    /// Apply material slot policy and write a diagnostic report.
    Report {
        /// Source FBX file.
        input: PathBuf,
        /// Optional material manifest used as explicit policy-layer input.
        #[arg(long)]
        manifest: Option<PathBuf>,
        /// Destination JSON report.
        #[arg(long)]
        out: PathBuf,
    },
    /// Serialize an RC import request and CryEngine multi-material.
    Convert {
        /// Source FBX file.
        input: PathBuf,
        /// Optional material manifest used as explicit policy-layer input.
        #[arg(long)]
        manifest: Option<PathBuf>,
        /// Optional CryEngine material override payload.
        #[arg(long)]
        overrides: Option<PathBuf>,
        /// Directory containing processed RC-ready texture outputs.
        #[arg(long)]
        texture_dir: Option<PathBuf>,
        /// Destination directory for request JSON and MTL.
        #[arg(long)]
        out_dir: PathBuf,
    },
    /// Validate a serialized RC import request and write a schema gate.
    Validate {
        /// RC import request JSON.
        input: PathBuf,
        /// Destination schema-gate JSON.
        #[arg(long)]
        out: Option<PathBuf>,
    },
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum FailureKind {
    Operational,
    Input,
    Gate,
}

#[derive(Debug)]
struct CliFailure {
    kind: FailureKind,
    message: String,
}

impl CliFailure {
    fn operational(message: impl Into<String>) -> Self {
        Self {
            kind: FailureKind::Operational,
            message: message.into(),
        }
    }

    fn input(message: impl Into<String>) -> Self {
        Self {
            kind: FailureKind::Input,
            message: message.into(),
        }
    }

    fn gate(message: impl Into<String>) -> Self {
        Self {
            kind: FailureKind::Gate,
            message: message.into(),
        }
    }

    fn exit_code(&self) -> ExitCode {
        ExitCode::from(match self.kind {
            FailureKind::Operational => 1,
            FailureKind::Input => 2,
            FailureKind::Gate => 3,
        })
    }
}

fn main() -> ExitCode {
    match run(Cli::parse()) {
        Ok(()) => ExitCode::SUCCESS,
        Err(error) => {
            eprintln!("error: {}", error.message);
            error.exit_code()
        }
    }
}

fn run(cli: Cli) -> Result<(), CliFailure> {
    match cli.command {
        Command::Dump { input, out } => {
            require_input_file(&input, "FBX input")?;
            converter::dump_file(&input, &out).map_err(classify_converter_error)
        }
        Command::Report {
            input,
            manifest,
            out,
        } => {
            require_input_file(&input, "FBX input")?;
            if let Some(path) = &manifest {
                require_input_file(path, "material manifest")?;
            }
            converter::report_file(&input, manifest.as_deref(), &out)
                .map_err(classify_converter_error)
        }
        Command::Convert {
            input,
            manifest,
            overrides,
            texture_dir,
            out_dir,
        } => {
            require_input_file(&input, "FBX input")?;
            if let Some(path) = &manifest {
                require_input_file(path, "material manifest")?;
            }
            if let Some(path) = &overrides {
                require_input_file(path, "material overrides")?;
            }
            if let Some(path) = &texture_dir {
                require_input_directory(path, "texture directory")?;
            }
            let outputs = converter::convert_file(
                &input,
                manifest.as_deref(),
                overrides.as_deref(),
                texture_dir.as_deref(),
                &out_dir,
            )
            .map_err(classify_converter_error)?;
            let json = serde_json::to_string_pretty(&outputs).map_err(|error| {
                CliFailure::operational(format!("failed to serialize output paths: {error}"))
            })?;
            println!("{json}");
            Ok(())
        }
        Command::Validate { input, out } => {
            require_input_file(&input, "request input")?;
            let out = out.unwrap_or_else(|| input.with_extension("schema_gate.json"));
            if converter::validate_file(&input, &out).map_err(classify_converter_error)? {
                Ok(())
            } else {
                Err(CliFailure::gate(format!(
                    "request schema gate failed: {}",
                    out.display()
                )))
            }
        }
    }
}

fn require_input_file(path: &std::path::Path, label: &str) -> Result<(), CliFailure> {
    match std::fs::metadata(path) {
        Ok(metadata) if metadata.is_file() => Ok(()),
        Ok(_) => Err(CliFailure::input(format!(
            "{label} is not a file: {}",
            path.display()
        ))),
        Err(error) => Err(CliFailure::input(format!(
            "cannot access {label} {}: {error}",
            path.display()
        ))),
    }
}

fn require_input_directory(path: &std::path::Path, label: &str) -> Result<(), CliFailure> {
    match std::fs::metadata(path) {
        Ok(metadata) if metadata.is_dir() => Ok(()),
        Ok(_) => Err(CliFailure::input(format!(
            "{label} is not a directory: {}",
            path.display()
        ))),
        Err(error) => Err(CliFailure::input(format!(
            "cannot access {label} {}: {error}",
            path.display()
        ))),
    }
}

fn classify_converter_error(message: String) -> CliFailure {
    if message.starts_with("failed to create ")
        || message.starts_with("failed to write ")
        || message.starts_with("failed to finish ")
        || message.starts_with("failed to serialize ")
    {
        CliFailure::operational(message)
    } else {
        CliFailure::input(message)
    }
}
