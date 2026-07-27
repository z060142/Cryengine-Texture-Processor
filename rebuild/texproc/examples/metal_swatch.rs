//! Metal-gate swatch atlas generator (T-014).
//!
//! Builds three synthetic input maps as one 512x2048 atlas:
//!   - X axis: metallic 0 -> 1 in 8 steps (64px cells)
//!   - Y axis: roughness 1 -> 0 in 8 steps, per basecolor block
//!   - four stacked basecolor blocks: white 240, iron-gray 196,
//!     gold (255,219,145), rust-orange (137,72,42)
//!
//! then runs the full pipeline twice (metal gate on with defaults, gate off)
//! and writes `_diff` / `_spec` / `_ddna` TIFFs plus PNG eyeball copies for both.
//!
//! This is a cargo *example*, not a CLI subcommand: the frozen `texproc` CLI
//! contract is untouched. Run from `rebuild/`:
//!
//!   cargo run -p texproc --release --example metal_swatch [OUT_DIR]
//!
//! OUT_DIR defaults to `fixtures/metal-swatch/` (gitignored).

use std::{
    env,
    error::Error,
    path::{Path, PathBuf},
};

use image::ExtendedColorType;
use texproc::{
    process_stage1, process_stage2, write_stage2_outputs, OutputTextures, PlanarImage, SourceImage,
    SourceTextures, TextureGroup, TextureSettings, TextureTypeSettings,
};

const CELL: u32 = 64;
const STEPS: u32 = 8; // metallic columns / roughness rows per block
const WIDTH: u32 = CELL * STEPS; // 512
const BLOCKS: u32 = 4; // basecolor rows stacked
const HEIGHT: u32 = CELL * STEPS * BLOCKS; // 2048

/// sRGB-encoded basecolors, top block first (design §4 / swatch spec).
const BASECOLORS: [[f32; 3]; BLOCKS as usize] = [
    [240.0 / 255.0, 240.0 / 255.0, 240.0 / 255.0], // white
    [196.0 / 255.0, 196.0 / 255.0, 196.0 / 255.0], // iron-gray
    [1.0, 219.0 / 255.0, 145.0 / 255.0],           // gold (255,219,145)
    [137.0 / 255.0, 72.0 / 255.0, 42.0 / 255.0],   // rust-orange
];

fn main() -> Result<(), Box<dyn Error>> {
    let out_dir = env::args()
        .nth(1)
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("fixtures/metal-swatch"));
    std::fs::create_dir_all(&out_dir)?;

    let sources = build_inputs()?;
    let types = TextureTypeSettings {
        diff: true,
        spec: true,
        ddna: true,
        displ: false,
        emissive: false,
        sss: false,
    };

    let mut written = Vec::new();
    for (base_name, gate) in [("metal_swatch_on", true), ("metal_swatch_off", false)] {
        let settings = TextureSettings {
            metal_gate: gate,
            texture_types: types,
            ..TextureSettings::default()
        };
        let mut group = TextureGroup {
            base_name: base_name.to_owned(),
            sources: sources.clone(),
            intermediate: Default::default(),
            output: OutputTextures::default(),
        };
        process_stage1(&mut group, &settings.intermediate_settings())?;
        process_stage2(&mut group, &settings)?;

        for path in write_stage2_outputs(&group.output, &out_dir)? {
            write_png_copy(&path, &group.output)?;
            written.push(path);
        }
    }

    println!("metal swatch atlas written to {}", out_dir.display());
    for path in &written {
        println!("  {}", path.display());
        println!("  {}", path.with_extension("png").display());
    }
    Ok(())
}

fn build_inputs() -> Result<SourceTextures, Box<dyn Error>> {
    let count = (WIDTH * HEIGHT) as usize;
    let mut diffuse = [
        Vec::with_capacity(count),
        Vec::with_capacity(count),
        Vec::with_capacity(count),
    ];
    let mut metallic = Vec::with_capacity(count);
    let mut roughness = Vec::with_capacity(count);

    for y in 0..HEIGHT {
        let block = (y / (CELL * STEPS)) as usize;
        let row = (y % (CELL * STEPS)) / CELL; // 0..STEPS
        let rough = 1.0 - row as f32 / (STEPS - 1) as f32; // roughness 1 -> 0 top to bottom
        let basecolor = BASECOLORS[block];
        for x in 0..WIDTH {
            let col = x / CELL; // 0..STEPS
            let metal = col as f32 / (STEPS - 1) as f32; // metallic 0 -> 1 left to right
            for channel in 0..3 {
                diffuse[channel].push(basecolor[channel]);
            }
            metallic.push(metal);
            roughness.push(rough);
        }
    }

    let diffuse = PlanarImage::new(WIDTH, HEIGHT, diffuse.to_vec())?;
    let metallic = PlanarImage::new(WIDTH, HEIGHT, vec![metallic])?;
    let roughness = PlanarImage::new(WIDTH, HEIGHT, vec![roughness])?;
    // Flat DirectX normal so a `_ddna` (normal + gloss alpha) is produced; the
    // gate never touches normal/gloss, so on/off ddna are identical by design.
    let normal = PlanarImage::new(
        WIDTH,
        HEIGHT,
        vec![vec![0.5; count], vec![0.5; count], vec![1.0; count]],
    )?;

    Ok(SourceTextures {
        diffuse: Some(SourceImage::new("swatch_diffuse.png", diffuse)),
        metallic: Some(SourceImage::new("swatch_metallic.png", metallic)),
        roughness: Some(SourceImage::new("swatch_roughness.png", roughness)),
        normal: Some(SourceImage::new("swatch_normal_dx.png", normal)),
        ..SourceTextures::default()
    })
}

fn write_png_copy(tiff_path: &Path, output: &OutputTextures) -> Result<(), Box<dyn Error>> {
    let image = [
        output.diff.as_ref(),
        output.spec.as_ref(),
        output.ddna.as_ref(),
    ]
    .into_iter()
    .flatten()
    .find(|image| tiff_path.ends_with(&image.filename))
    .map(|image| &image.image)
    .ok_or("no output image matches the written TIFF path")?;

    let color = match image.channels() {
        1 => ExtendedColorType::L8,
        2 => ExtendedColorType::La8,
        3 => ExtendedColorType::Rgb8,
        _ => ExtendedColorType::Rgba8,
    };
    image::save_buffer(
        tiff_path.with_extension("png"),
        &image.to_interleaved_u8(),
        image.width,
        image.height,
        color,
    )?;
    Ok(())
}
