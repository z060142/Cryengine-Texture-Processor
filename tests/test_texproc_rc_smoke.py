import struct
from pathlib import Path
from types import SimpleNamespace

from tools import texproc_rc_smoke


def _write_dxt5_dds(path, *, width=4, height=4):
    data = bytearray(128)
    data[:4] = b"DDS "
    struct.pack_into("<7I", data, 4, 124, 0x0002100F, height, width, 16, 0, 1)
    struct.pack_into("<2I", data, 76, 32, 0x4)
    data[84:88] = b"DXT5"
    struct.pack_into("<5I", data, 88, 0, 0, 0, 0, 0)
    struct.pack_into("<5I", data, 108, 0x1000, 0, 0, 0, 0)
    path.write_bytes(data)


def _write_dxt1_dds(path, *, width=4, height=4):
    data = bytearray(128)
    data[:4] = b"DDS "
    struct.pack_into("<7I", data, 4, 124, 0x0002100F, height, width, 8, 0, 1)
    struct.pack_into("<2I", data, 76, 32, 0x4)
    data[84:88] = b"DXT1"
    struct.pack_into("<5I", data, 88, 0, 0, 0, 0, 0)
    struct.pack_into("<5I", data, 108, 0x1000, 0, 0, 0, 0)
    path.write_bytes(data)


def _write_cry_attached_alpha_dds(path, *, width=4, height=4):
    data = bytearray(148)
    data[:4] = b"DDS "
    struct.pack_into("<7I", data, 4, 124, 0x0002100F, height, width, 16, 0, 1)
    struct.pack_into("<I", data, 36, texproc_rc_smoke.CRY_EIF_ATTACHED_ALPHA)
    struct.pack_into("<2I", data, 76, 32, 0x4)
    data[84:88] = b"DX10"
    struct.pack_into("<5I", data, 88, 0, 0, 0, 0, 0)
    struct.pack_into("<4I", data, 108, 0x1000, 0, 0, 0)
    data[124:128] = b"FYRC"
    struct.pack_into("<5I", data, 128, 84, 3, 0, 1, 0)
    path.write_bytes(data)


def test_rc_command_freezes_texture_flags():
    assert texproc_rc_smoke.build_rc_command(
        "S:/Tools/rc/rc.exe", "C:/work/asset_ddna.tif"
    ) == [
        "S:/Tools/rc/rc.exe",
        "C:/work/asset_ddna.tif",
        "/refresh",
        "/userdialog=0",
    ]


def test_dds_header_detects_alpha_capable_fourcc(tmp_path):
    dxt5 = tmp_path / "normal_ddna.dds"
    dxt1 = tmp_path / "surface_diff.dds"
    attached = tmp_path / "normal_attached_alpha.dds"
    _write_dxt5_dds(dxt5)
    _write_dxt1_dds(dxt1)
    _write_cry_attached_alpha_dds(attached)

    alpha = texproc_rc_smoke.read_dds_header(dxt5)
    opaque = texproc_rc_smoke.read_dds_header(dxt1)
    cry_alpha = texproc_rc_smoke.read_dds_header(attached)
    assert alpha["fourcc"] == "DXT5"
    assert alpha["alpha_capable"] is True
    assert alpha["alpha_reasons"] == ["fourcc:DXT5"]
    assert opaque["fourcc"] == "DXT1"
    assert opaque["alpha_capable"] is False
    assert cry_alpha["fourcc"] == "DX10"
    assert cry_alpha["dxgi_format"] == 84
    assert cry_alpha["cry_texture_stage"] == "FYRC"
    assert cry_alpha["cry_image_flags"] == 0x400
    assert cry_alpha["cry_attached_alpha"] is True
    assert cry_alpha["alpha_reasons"] == ["cry_eif_attached_alpha"]


def test_smoke_requires_every_dds_and_ddna_alpha(monkeypatch, tmp_path):
    rc_exe = tmp_path / "rc.exe"
    texproc_exe = tmp_path / "texproc.exe"
    source = tmp_path / "source.png"
    for path in [rc_exe, texproc_exe, source]:
        path.write_bytes(b"fixture")
    work_dir = tmp_path / "work"
    report_path = tmp_path / "report.json"

    def fake_run(command, cwd=None):
        if command[0] == str(texproc_exe):
            output = work_dir / "textures"
            (output / "Asset_diff.tif").write_bytes(b"tiff")
            (output / "Asset_ddna.tif").write_bytes(b"tiff")
        else:
            _write_dxt5_dds(Path(command[1]).with_suffix(".dds"))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(texproc_rc_smoke, "_run", fake_run)
    report = texproc_rc_smoke.run_smoke(
        rc_exe=rc_exe,
        texproc_exe=texproc_exe,
        inputs=[source],
        work_dir=work_dir,
        output_path=report_path,
    )

    assert report["summary"] == {
        "ok": True,
        "input_count": 1,
        "tif_count": 2,
        "rc_success_count": 2,
        "dds_count": 2,
        "dds_header_ok_count": 2,
        "ddna_count": 1,
        "ddna_alpha_ok_count": 1,
    }
    assert report_path.is_file()
    assert (work_dir / "VISUAL_CHECK.md").is_file()
