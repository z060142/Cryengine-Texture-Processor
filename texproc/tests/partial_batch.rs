use std::{fs, process::Command};

#[test]
fn cli_processes_valid_textures_before_reporting_unassigned_or_missing_inputs() {
    let root = std::env::temp_dir().join(format!("texproc-cli-partial-{}-{}", std::process::id(),
        std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_nanos()));
    fs::create_dir_all(&root).unwrap();
    let valid = root.join("Wall_diff.png");
    image::RgbImage::new(2, 2).save(&valid).unwrap();
    let unknown = root.join("unassigned.png");
    image::RgbImage::new(2, 2).save(&unknown).unwrap();
    let output = root.join("out");
    let result = Command::new(env!("CARGO_BIN_EXE_texproc"))
        .arg("process").arg("--out").arg(&output)
        .arg(&valid).arg(&unknown).arg(root.join("Missing_rough.exr"))
        .output().unwrap();
    assert_eq!(result.status.code(), Some(3));
    assert!(output.join("Wall_diff.tif").is_file());
    let stderr = String::from_utf8_lossy(&result.stderr);
    assert!(stderr.contains("Missing_rough.exr"), "{stderr}");
    assert!(stderr.contains("unassigned.png"), "{stderr}");
    fs::remove_dir_all(root).unwrap();
}
