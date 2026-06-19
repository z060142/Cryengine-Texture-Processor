import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from ui_pyside.export_settings import ExportSettingsPanel


def _app():
    return QApplication.instance() or QApplication([])


class FakeMainWindow:
    def __init__(self, texture_result):
        self.texture_result = texture_result
        self.texture_calls = 0
        self.mtl_calls = 0
        self.fbx_calls = 0

    def start_batch_processing(self, **kwargs):
        self.texture_calls += 1
        self.last_texture_kwargs = kwargs
        return self.texture_result

    def run_model_mtl_export(self, *args, **kwargs):
        del args, kwargs
        self.mtl_calls += 1
        raise AssertionError("MTL export should not run after texture export failure")

    def run_model_fbx_export(self, *args, **kwargs):
        del args, kwargs
        self.fbx_calls += 1
        raise AssertionError("FBX export should not run after texture export failure")


def _panel(tmp_path, monkeypatch, fake_main_window):
    _app()
    panel = ExportSettingsPanel()
    panel.set_settings(
        {
            "texture_output_directory": str(tmp_path / "textures"),
            "model_output_directory": str(tmp_path / "models"),
        }
    )
    monkeypatch.setattr(panel, "_main_window", lambda: fake_main_window)
    return panel


def test_batch_process_stops_model_export_when_texture_gate_fails(tmp_path, monkeypatch):
    fake_main_window = FakeMainWindow(texture_result=False)
    panel = _panel(tmp_path, monkeypatch, fake_main_window)
    summaries = []
    monkeypatch.setattr(panel, "_show_export_summary", lambda *args: summaries.append(args))

    panel._on_batch_process()

    assert fake_main_window.texture_calls == 1
    assert fake_main_window.mtl_calls == 0
    assert fake_main_window.fbx_calls == 0
    assert summaries == [
        (0, 0, 1, ["Texture export failed; model export was skipped."]),
    ]
    panel.close()


def test_export_textures_stops_cleanup_path_after_texture_gate_fails(tmp_path, monkeypatch):
    fake_main_window = FakeMainWindow(texture_result=False)
    panel = _panel(tmp_path, monkeypatch, fake_main_window)

    panel.export_textures(texture_groups=["selected-group"])

    assert fake_main_window.texture_calls == 1
    assert fake_main_window.last_texture_kwargs["texture_groups"] == ["selected-group"]
    assert fake_main_window.mtl_calls == 0
    assert fake_main_window.fbx_calls == 0
    assert panel._new_generated_files is None
    panel.close()


def test_output_format_options_are_limited_to_rc_source_format(tmp_path, monkeypatch):
    fake_main_window = FakeMainWindow(texture_result=True)
    panel = _panel(tmp_path, monkeypatch, fake_main_window)

    assert [panel.format_combo.itemText(index) for index in range(panel.format_combo.count())] == ["tif"]

    panel.set_settings({"output_format": "png"})
    assert panel.get_settings()["output_format"] == "tif"
    panel.close()
