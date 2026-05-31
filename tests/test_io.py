import csv

from ht2sim.core.session import Halt, ReadPage, StartAuth, WritePage
from ht2sim.io.export import export_frames_csv, export_waveform_csv
from ht2sim.io.scenario_io import (
    load_scenario,
    save_scenario,
    scenario_from_dict,
    scenario_to_dict,
)
from ht2sim.core.scenario import Scenario, TagConfig


def sample_scenario() -> Scenario:
    return Scenario(
        tag=TagConfig(ide=0x12345610, psw_b=0x4D494B52, tmcf=0x07, psw_t=0xAA4854,
                      user=[0x11111111, 0, 0, 0xDEADBEEF]),
        program=[StartAuth(0x4D494B52), ReadPage(0), WritePage(4, 0xCAFEBABE), Halt()],
    )


def test_scenario_dict_roundtrip_preserves_everything():
    scn = sample_scenario()
    back = scenario_from_dict(scenario_to_dict(scn))
    assert back.tag == scn.tag
    assert back.program == scn.program


def test_tmcf_dcs_survives_roundtrip_as_cdp():
    scn = sample_scenario()
    back = scenario_from_dict(scenario_to_dict(scn))
    assert back.tag.coding.value == "cdp"


def test_save_and_load_file(tmp_path):
    scn = sample_scenario()
    path = tmp_path / "scn.json"
    save_scenario(scn, str(path))
    loaded = load_scenario(str(path))
    assert loaded.tag == scn.tag
    assert loaded.program == scn.program


def test_hex_strings_are_human_readable(tmp_path):
    scn = sample_scenario()
    path = tmp_path / "scn.json"
    save_scenario(scn, str(path))
    text = path.read_text()
    assert "0x4D494B52" in text


def test_load_rejects_unknown_version():
    import pytest

    with pytest.raises(ValueError):
        scenario_from_dict({"version": 999, "tag": {}, "program": []})


def test_frames_csv_has_row_per_frame(tmp_path):
    result = sample_scenario().run()
    path = tmp_path / "frames.csv"
    export_frames_csv(result, str(path))
    rows = list(csv.DictReader(path.open()))
    assert len(rows) == len(result.frames)
    assert rows[0]["label"].startswith("START_AUTH")
    assert rows[0]["direction"] == "reader->tag"


def test_waveform_csv_columns_and_levels(tmp_path):
    scn = sample_scenario()
    result = scn.run()
    path = tmp_path / "wave.csv"
    export_waveform_csv(result, scn.tag.coding, str(path), samples_per_to=4.0)
    reader = csv.DictReader(path.open())
    assert reader.fieldnames == ["t_to", "t_us", "reader", "tag"]
    rows = list(reader)
    assert len(rows) > 0
    for r in rows:
        assert 0.0 <= float(r["reader"]) <= 1.0
        assert 0.0 <= float(r["tag"]) <= 1.0
