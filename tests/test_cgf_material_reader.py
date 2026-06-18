import os
import struct

from utils.cgf_material_reader import read_cgf_material_summary, read_chunk_table


def _write_synthetic_cgf(path):
    header_size = 16
    table_entry_size = 16
    chunk_count = 2
    chunk_table_offset = header_size
    data_offset = header_size + table_entry_size * chunk_count

    mesh_chunk_id = 10
    subset_chunk_id = 11
    mesh_chunk = struct.pack("<7i", 0, 0, 4, 6, 2, subset_chunk_id, -1) + (b"\0" * (264 - 28))
    subset_header = struct.pack("<4i", 0, 2, 0, 0)
    subset_0 = struct.pack("<5if3f", 0, 3, 0, 3, 0, 1.0, 0.0, 0.0, 0.0)
    subset_1 = struct.pack("<5if3f", 3, 3, 1, 3, 2, 1.0, 1.0, 0.0, 0.0)
    subset_chunk = subset_header + subset_0 + subset_1

    mesh_offset = data_offset
    subset_offset = mesh_offset + len(mesh_chunk)
    entries = [
        struct.pack("<HHIII", 0x1000, 0x0801, mesh_chunk_id, len(mesh_chunk), mesh_offset),
        struct.pack("<HHIII", 0x1017, 0x0800, subset_chunk_id, len(subset_chunk), subset_offset),
    ]

    path.write_bytes(
        struct.pack("<4sIII", b"CrCh", 0x746, chunk_count, chunk_table_offset)
        + b"".join(entries)
        + mesh_chunk
        + subset_chunk
    )


def test_read_chunk_table_reads_0x746_entries(tmp_path):
    cgf_path = tmp_path / "asset.cgf"
    _write_synthetic_cgf(cgf_path)

    chunks = read_chunk_table(str(cgf_path))

    assert [chunk.type_name for chunk in chunks] == ["Mesh", "MeshSubsets"]
    assert chunks[0].chunk_id == 10
    assert chunks[1].chunk_id == 11


def test_read_cgf_material_summary_reads_mesh_subset_material_ids(tmp_path):
    cgf_path = tmp_path / "asset.cgf"
    _write_synthetic_cgf(cgf_path)

    summary = read_cgf_material_summary(str(cgf_path))

    assert summary["chunk_count"] == 2
    assert summary["material_ids"] == [0, 2]
    assert summary["meshes"][0]["subsets_chunk_id"] == 11
    assert summary["meshes"][0]["subsets"] == [
        {
            "subset": 0,
            "first_index": 0,
            "num_indices": 3,
            "first_vert": 0,
            "num_verts": 3,
            "material_id": 0,
            "radius": 1.0,
            "center": [0.0, 0.0, 0.0],
        },
        {
            "subset": 1,
            "first_index": 3,
            "num_indices": 3,
            "first_vert": 1,
            "num_verts": 3,
            "material_id": 2,
            "radius": 1.0,
            "center": [1.0, 0.0, 0.0],
        },
    ]


def test_read_chunk_table_rejects_unsupported_signature(tmp_path):
    cgf_path = tmp_path / "bad.cgf"
    cgf_path.write_bytes(b"bad!" + (b"\0" * 12))

    try:
        read_chunk_table(str(cgf_path))
    except ValueError as e:
        assert "Unsupported CGF signature" in str(e)
    else:
        raise AssertionError("Expected unsupported signature error")


def test_synthetic_cgf_size_is_consistent(tmp_path):
    cgf_path = tmp_path / "asset.cgf"
    _write_synthetic_cgf(cgf_path)

    assert os.path.getsize(cgf_path) > 0
