import json
import struct

from tools.cgf_material_probe import main


def _write_synthetic_cgf(path):
    mesh_chunk_id = 10
    subset_chunk_id = 11
    mesh_chunk = struct.pack("<7i", 0, 0, 4, 3, 1, subset_chunk_id, -1) + (b"\0" * (264 - 28))
    subset_chunk = struct.pack("<4i", 0, 1, 0, 0) + struct.pack("<5if3f", 0, 3, 0, 3, 5, 1.0, 0.0, 0.0, 0.0)

    header_size = 16
    table_entry_size = 16
    chunk_count = 2
    table_offset = header_size
    mesh_offset = header_size + table_entry_size * chunk_count
    subset_offset = mesh_offset + len(mesh_chunk)

    path.write_bytes(
        struct.pack("<4sIII", b"CrCh", 0x746, chunk_count, table_offset)
        + struct.pack("<HHIII", 0x1000, 0x0801, mesh_chunk_id, len(mesh_chunk), mesh_offset)
        + struct.pack("<HHIII", 0x1017, 0x0800, subset_chunk_id, len(subset_chunk), subset_offset)
        + mesh_chunk
        + subset_chunk
    )


def test_cgf_material_probe_prints_summary(tmp_path, capsys):
    cgf_path = tmp_path / "asset.cgf"
    _write_synthetic_cgf(cgf_path)

    assert main([str(cgf_path)]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["material_ids"] == [5]
