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
    Convert,
    Validate,
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
        Command::Convert | Command::Validate => Err("not implemented".to_owned()),
    }
}
