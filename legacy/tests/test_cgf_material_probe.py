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


def _write_synthetic_cgf_with_mtl_name(path):
    mtl_chunk_id = 2
    name = b"car_body"
    header = name + (b"\0" * (128 - len(name))) + struct.pack("<i", 2)
    physicalize_types = struct.pack("<2i", 0, 1)
    sub_names = b"Paint\0Glass\0"
    mtl_chunk = header + physicalize_types + sub_names

    header_size = 16
    table_entry_size = 16
    chunk_count = 1
    table_offset = header_size
    mtl_offset = header_size + table_entry_size * chunk_count

    path.write_bytes(
        struct.pack("<4sIII", b"CrCh", 0x746, chunk_count, table_offset)
        + struct.pack("<HHIII", 0x1014, 0x0802, mtl_chunk_id, len(mtl_chunk), mtl_offset)
        + mtl_chunk
    )


def _write_synthetic_cgf_with_import_settings(path):
    settings_chunk_id = 3
    settings_chunk = (
        b'{"version":1,"source_filename":"asset.fbx",'
        b'"materials":[{"name":"Paint","physicalize":"no","sub_index":0}]}'
    )

    header_size = 16
    table_entry_size = 16
    chunk_count = 1
    table_offset = header_size
    settings_offset = header_size + table_entry_size * chunk_count

    path.write_bytes(
        struct.pack("<4sIII", b"CrCh", 0x746, chunk_count, table_offset)
        + struct.pack("<HHIII", 0x1019, 0, settings_chunk_id, len(settings_chunk), settings_offset)
        + settings_chunk
    )


def test_cgf_material_probe_prints_summary(tmp_path, capsys):
    cgf_path = tmp_path / "asset.cgf"
    _write_synthetic_cgf(cgf_path)

    assert main([str(cgf_path)]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["material_ids"] == [5]


def test_cgf_material_probe_reads_mtl_name_chunk_0802(tmp_path, capsys):
    cgf_path = tmp_path / "asset.cgf"
    _write_synthetic_cgf_with_mtl_name(cgf_path)

    assert main([str(cgf_path)]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["materials"] == [
        {
            "chunk_id": 2,
            "name": "car_body",
            "sub_material_count": 2,
            "physicalize_types": [0, 1],
            "sub_materials": [
                {"slot": 0, "name": "Paint", "physicalize_type": 0},
                {"slot": 1, "name": "Glass", "physicalize_type": 1},
            ],
        }
    ]


def test_cgf_material_probe_reads_import_settings_chunk(tmp_path, capsys):
    cgf_path = tmp_path / "asset.cgf"
    _write_synthetic_cgf_with_import_settings(cgf_path)

    assert main([str(cgf_path)]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["import_settings"][0]["chunk_id"] == 3
    assert output["import_settings"][0]["json_error"] == ""
    assert output["import_settings"][0]["json"]["source_filename"] == "asset.fbx"
    assert output["import_settings"][0]["json"]["materials"] == [
        {"name": "Paint", "physicalize": "no", "sub_index": 0}
    ]
