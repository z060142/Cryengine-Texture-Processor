use std::fs;
use std::path::{Path, PathBuf};
use std::process::{Command, Output};
use std::time::{SystemTime, UNIX_EPOCH};

fn converter() -> &'static str {
    env!("CARGO_BIN_EXE_converter")
}

fn fixture(path: &str) -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("..").join(path)
}

fn temp_dir(label: &str) -> PathBuf {
    let unique = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_nanos();
    let path = std::env::temp_dir().join(format!("converter-cli-{label}-{unique}"));
    fs::create_dir_all(&path).unwrap();
    path
}

fn run(args: &[&str]) -> Output {
    Command::new(converter()).args(args).output().unwrap()
}

#[test]
fn top_level_help_freezes_exit_code_contract() {
    let output = run(&["--help"]);
    assert_eq!(output.status.code(), Some(0));
    let stdout = String::from_utf8_lossy(&output.stdout);
    assert!(stdout.contains("EXIT CODES:"));
    assert!(stdout.contains("3  Request schema gate failed"));
}

#[test]
fn convert_help_includes_preserve_mtl_contract() {
    let output = run(&["convert", "--help"]);
    assert_eq!(output.status.code(), Some(0));
    let stdout = String::from_utf8_lossy(&output.stdout);
    assert!(stdout.contains("--preserve-mtl-textures"));
    assert!(stdout.contains("reference MTL"));
}

#[test]
fn clap_argument_errors_exit_two() {
    let output = run(&["dump"]);
    assert_eq!(output.status.code(), Some(2));
}

#[test]
fn missing_input_exits_two() {
    let root = temp_dir("missing-input");
    let missing = root.join("missing.fbx");
    let out = root.join("dump.json");
    let output = Command::new(converter())
        .args(["dump"])
        .arg(&missing)
        .args(["--out"])
        .arg(&out)
        .output()
        .unwrap();
    assert_eq!(output.status.code(), Some(2));
    fs::remove_dir_all(root).unwrap();
}

#[test]
fn schema_gate_failure_exits_three_and_writes_gate() {
    let root = temp_dir("gate-failure");
    let request = root.join("invalid.json");
    let gate = root.join("invalid.schema_gate.json");
    fs::write(&request, "{}").unwrap();
    let output = Command::new(converter())
        .arg("validate")
        .arg(&request)
        .args(["--out"])
        .arg(&gate)
        .output()
        .unwrap();
    assert_eq!(output.status.code(), Some(3));
    let payload = fs::read_to_string(&gate).unwrap();
    assert!(payload.contains("\"ok\": false"));
    fs::remove_dir_all(root).unwrap();
}

#[test]
fn output_io_failure_exits_one() {
    let request = fixture("fixtures/car/car-reference.request.json");
    let root = temp_dir("output-error");
    let output = Command::new(converter())
        .arg("validate")
        .arg(&request)
        .args(["--out"])
        .arg(&root)
        .output()
        .unwrap();
    assert_eq!(output.status.code(), Some(1));
    fs::remove_dir_all(root).unwrap();
}

#[test]
fn missing_preserve_mtl_reference_exits_two() {
    let root = temp_dir("missing-preserve-reference");
    let fbx = fixture("fixtures/car/car.fbx");
    let missing = root.join("missing.mtl");
    let output = Command::new(converter())
        .arg("convert")
        .arg(&fbx)
        .args(["--preserve-mtl-textures"])
        .arg(&missing)
        .args(["--out-dir"])
        .arg(&root)
        .output()
        .unwrap();
    assert_eq!(output.status.code(), Some(2));
    assert!(String::from_utf8_lossy(&output.stderr).contains("preserve-MTL reference"));
    fs::remove_dir_all(root).unwrap();
}
