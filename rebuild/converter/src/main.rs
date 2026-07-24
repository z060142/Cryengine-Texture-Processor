use clap::{Parser, Subcommand};
use std::process::ExitCode;

#[derive(Parser)]
#[command(version, about = "CryEngine FBX converter")]
struct Cli {
    #[command(subcommand)]
    command: Command,
}

#[derive(Subcommand)]
enum Command {
    Dump,
    Convert,
    Validate,
}

fn main() -> ExitCode {
    let cli = Cli::parse();

    match cli.command {
        Command::Dump | Command::Convert | Command::Validate => {
            eprintln!("not implemented");
            ExitCode::from(2)
        }
    }
}
