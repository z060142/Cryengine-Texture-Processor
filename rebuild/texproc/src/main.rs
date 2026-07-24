use clap::{Parser, Subcommand};
use std::process::ExitCode;

#[derive(Parser)]
#[command(version, about = "CryEngine texture processor")]
struct Cli {
    #[command(subcommand)]
    command: Command,
}

#[derive(Subcommand)]
enum Command {
    Scan,
    Process,
}

fn main() -> ExitCode {
    let cli = Cli::parse();

    match cli.command {
        Command::Scan | Command::Process => {
            eprintln!("not implemented");
            ExitCode::from(2)
        }
    }
}
