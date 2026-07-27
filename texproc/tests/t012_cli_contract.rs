use std::{
    fs,
    path::{Path, PathBuf},
    process::{Command, Output},
    sync::atomic::{AtomicUsize, Ordering},
};

use image::{ColorType, ImageFormat};
use serde_json::Value;

static SEQUENCE: AtomicUsize = AtomicUsize::new(0);

struct TempDir(PathBuf);

impl TempDir {
    fn new() -> Self {
        let sequence = SEQUENCE.fetch_add(1, Ordering::Relaxed);
        let path =
            std::env::temp_dir().join(format!("texproc-t012-{}-{sequence}", std::process::id()));
        fs::create_dir_all(&path).unwrap();
        Self(path)
    }
}

impl Drop for TempDir {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.0);
    }
}

fn texproc(args: &[&str]) -> Output {
    Command::new(env!("CARGO_BIN_EXE_texproc"))
        .args(args)
        .output()
        .unwrap()
}

fn save_rgb(path: &Path, width: u32, height: u32, rgb: [u8; 3]) {
    let pixels = rgb.repeat((width * height) as usize);
    image::save_buffer_with_format(
        path,
        &pixels,
        width,
        height,
        ColorType::Rgb8,
        ImageFormat::Png,
    )
    .unwrap();
}

fn save_gray(path: &Path, width: u32, height: u32, value: u8) {
    let pixels = vec![value; (width * height) as usize];
    image::save_buffer_with_format(
        path,
        &pixels,
        width,
        height,
        ColorType::L8,
        ImageFormat::Png,
    )
    .unwrap();
}

#[test]
fn help_freezes_commands_flags_and_exit_codes() {
    let top = texproc(&["--help"]);
    assert!(top.status.success());
    let top = String::from_utf8(top.stdout).unwrap();
    for expected in ["scan", "process", "EXIT CODES:", "3  grouping gate failure"] {
        assert!(top.contains(expected), "missing `{expected}` from:\n{top}");
    }

    let scan = String::from_utf8(texproc(&["scan", "--help"]).stdout).unwrap();
    for expected in ["--suffixes", "--out", "<INPUTS>..."] {
        assert!(
            scan.contains(expected),
            "missing `{expected}` from:\n{scan}"
        );
    }
    let process = String::from_utf8(texproc(&["process", "--help"]).stdout).unwrap();
    for expected in [
        "--settings",
        "--suffixes",
        "--groups",
        "--out",
        "--allow-unknown",
    ] {
        assert!(
            process.contains(expected),
            "missing `{expected}` from:\n{process}"
        );
    }
}

#[test]
fn scan_is_deterministic_and_process_consumes_reviewed_groups() {
    let temp = TempDir::new();
    let input = temp.0.join("input");
    let output = temp.0.join("output");
    let groups = temp.0.join("groups.json");
    fs::create_dir(&input).unwrap();
    save_rgb(&input.join("Stone_diff.png"), 2, 2, [128, 96, 64]);
    save_rgb(&input.join("stone_normal.png"), 2, 2, [128, 128, 255]);
    save_gray(&input.join("STONE_roughness.png"), 2, 2, 160);
    save_gray(&input.join("Stone_height.png"), 2, 2, 32);

    let scan = texproc(&[
        "scan",
        "--out",
        groups.to_str().unwrap(),
        input.to_str().unwrap(),
    ]);
    assert!(
        scan.status.success(),
        "{}",
        String::from_utf8_lossy(&scan.stderr)
    );
    let json: Value = serde_json::from_slice(&fs::read(&groups).unwrap()).unwrap();
    assert_eq!(json["groups"].as_array().unwrap().len(), 1);
    assert_eq!(json["groups"][0]["base_name"], "Stone");
    assert_eq!(json["groups"][0]["slots"].as_object().unwrap().len(), 4);
    assert_eq!(
        json["groups"][0]["slots"]["diffuse"]["header"]["channels"],
        3
    );

    let process = texproc(&[
        "process",
        "--groups",
        groups.to_str().unwrap(),
        "--out",
        output.to_str().unwrap(),
    ]);
    assert!(
        process.status.success(),
        "{}",
        String::from_utf8_lossy(&process.stderr)
    );
    for suffix in ["diff", "spec", "ddna", "displ"] {
        assert!(output.join(format!("Stone_{suffix}.tif")).is_file());
    }
    assert!(String::from_utf8_lossy(&process.stderr).contains("rayon thread(s)"));
}

#[test]
fn unknown_only_group_uses_exit_three_and_allow_unknown_overrides_it() {
    let temp = TempDir::new();
    let input = temp.0.join("mystery.png");
    let output = temp.0.join("output");
    save_rgb(&input, 1, 1, [1, 2, 3]);

    let blocked = texproc(&[
        "process",
        "--out",
        output.to_str().unwrap(),
        input.to_str().unwrap(),
    ]);
    assert_eq!(blocked.status.code(), Some(3));
    assert!(String::from_utf8_lossy(&blocked.stderr).contains("unknown-only group"));

    let allowed = texproc(&[
        "process",
        "--allow-unknown",
        "--out",
        output.to_str().unwrap(),
        input.to_str().unwrap(),
    ]);
    assert!(
        allowed.status.success(),
        "{}",
        String::from_utf8_lossy(&allowed.stderr)
    );
}

#[test]
fn invalid_configuration_uses_exit_two() {
    let temp = TempDir::new();
    let groups = temp.0.join("groups.json");
    let settings = temp.0.join("settings.json");
    let output = temp.0.join("output");
    fs::write(&groups, r#"{"version":1,"groups":[],"diagnostics":[]}"#).unwrap();
    fs::write(&settings, r#"{"output_resolution":"0"}"#).unwrap();

    let invalid_settings = texproc(&[
        "process",
        "--groups",
        groups.to_str().unwrap(),
        "--settings",
        settings.to_str().unwrap(),
        "--out",
        output.to_str().unwrap(),
    ]);
    assert_eq!(invalid_settings.status.code(), Some(2));

    let mixed_inputs = texproc(&[
        "process",
        "--groups",
        groups.to_str().unwrap(),
        "--out",
        output.to_str().unwrap(),
        groups.to_str().unwrap(),
    ]);
    assert_eq!(mixed_inputs.status.code(), Some(2));
}
