import json
import subprocess
import sys

from tools.converter_schema import (
    build_converter_schema,
    check_converter_schema_snapshot,
    converter_schema_json,
    write_converter_schema,
)


def test_build_converter_schema_exports_external_tool_contract():
    schema = build_converter_schema()

    assert schema["schema"] == "cryengine_converter_schema.v1"
    assert [rule["id"] for rule in schema["material_slot_mapping"]["rules"]] == [
        "request_sub_index_is_final_slot",
        "mtl_child_order_matches_final_slots",
        "cgf_subset_material_id_indexes_final_slots",
        "raw_fbx_id_is_one_based",
        "sub_index_limit",
    ]

    output_by_key = {
        output["output_key"]: output
        for output in schema["texture_outputs"]["outputs"]
    }
    assert output_by_key["diff"]["ce_map_type"] == "Diffuse"
    assert output_by_key["diff"]["expected_suffix"] == "_diff"
    assert output_by_key["ddna"]["ce_map_type"] == "Bumpmap"
    assert output_by_key["ddna"]["accepted_suffixes"] == ["_ddn", "_ddna"]
    assert schema["texture_outputs"]["supported_source_extensions"] == ["dds", "hdr", "tif"]

    texture_entries = {
        entry["texture_type"]: entry
        for entry in schema["mtl"]["texture_maps"]["entries"]
    }
    assert texture_entries["diffuse"]["ce_map_type"] == "Diffuse"
    assert texture_entries["diffuse"]["exported"] is True
    assert texture_entries["ao"]["exported"] is False
    assert texture_entries["ao"]["reason"] == "known_internal_non_mtl_channel"
    assert texture_entries["glossiness"]["exported"] is False

    attrs = schema["mtl"]["material_attributes"]["attributes"]
    assert attrs["Shader"] == "Illum"
    assert attrs["Opacity"] == "1"
    assert schema["mtl"]["mtl_flags"]["sub_material"]["mtl_flags"] == "524416"
    assert "%NORMAL_MAP" in schema["mtl"]["shader_policy"]["normal_specular_displacement"]["tokens"]


def test_write_converter_schema_writes_json(tmp_path):
    output_path = write_converter_schema(build_converter_schema(), str(tmp_path / "converter_schema.json"))

    written = json.loads((tmp_path / "converter_schema.json").read_text(encoding="utf-8"))
    assert output_path == str(tmp_path / "converter_schema.json")
    assert written["schema"] == "cryengine_converter_schema.v1"
    assert (tmp_path / "converter_schema.json").read_text(encoding="utf-8") == converter_schema_json(
        build_converter_schema()
    )


def test_check_converter_schema_snapshot_reports_current_and_stale(tmp_path):
    schema = build_converter_schema()
    snapshot = tmp_path / "converter_schema.json"
    snapshot.write_text(converter_schema_json(schema), encoding="utf-8")

    assert check_converter_schema_snapshot(schema, str(snapshot)) == {
        "ok": True,
        "path": str(snapshot),
        "error": "",
        "message": "Converter schema snapshot is current.",
    }

    snapshot.write_text(json.dumps({"schema": "stale"}, indent=2) + "\n", encoding="utf-8")
    result = check_converter_schema_snapshot(schema, str(snapshot))
    assert result["ok"] is False
    assert result["path"] == str(snapshot)
    assert result["error"] == ""
    assert "stale" in result["message"]


def test_converter_schema_cli_check_accepts_current_snapshot(tmp_path):
    snapshot = tmp_path / "converter_schema.json"
    write_converter_schema(build_converter_schema(), str(snapshot))

    result = subprocess.run(
        [sys.executable, "tools/converter_schema.py", "--check", str(snapshot)],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert payload["ok"] is True
