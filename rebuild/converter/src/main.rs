use clap::{Parser, Subcommand};
use std::path::PathBuf;
use std::process::ExitCode;

#[derive(Parser)]
#[command(version, about = "CryEngine FBX converter")]
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

fn main() -> ExitCode {
    match run(Cli::parse()) {
        Ok(()) => ExitCode::SUCCESS,
        Err(error) => {
            eprintln!("error: {error}");
            ExitCode::FAILURE
        }
    }
}

fn run(cli: Cli) -> Result<(), String> {
    match cli.command {
        Command::Dump { input, out } => converter::dump_file(&input, &out),
        Command::Report {
            input,
            manifest,
            out,
        } => converter::report_file(&input, manifest.as_deref(), &out),
        Command::Convert {
            input,
            manifest,
            overrides,
            out_dir,
        } => {
            let outputs = converter::convert_file(
                &input,
                manifest.as_deref(),
                overrides.as_deref(),
                &out_dir,
            )?;
            let json = serde_json::to_string_pretty(&outputs)
                .map_err(|error| format!("failed to serialize output paths: {error}"))?;
            println!("{json}");
            Ok(())
        }
        Command::Validate { input, out } => {
            let out = out.unwrap_or_else(|| input.with_extension("schema_gate.json"));
            if converter::validate_file(&input, &out)? {
                Ok(())
            } else {
                Err(format!("request schema gate failed: {}", out.display()))
            }
        }
    }
}
