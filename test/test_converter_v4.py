import io
from lxml import objectify
import pathlib
import pytest
import tempfile

from hpxml_version_translator.converter import (
    convert_hpxml4_to_5,
    convert_hpxml_to_version,
)
from hpxml_version_translator import exceptions as exc


hpxml_dir = pathlib.Path(__file__).resolve().parent / "hpxml_v4_files"


def convert_hpxml_and_parse(input_filename, version="5.0"):
    with tempfile.NamedTemporaryFile("w+b") as f_out:
        convert_hpxml_to_version(version, input_filename, f_out)
        f_out.seek(0)
        root = objectify.parse(f_out).getroot()
    return root


def test_version_change_to_4():
    root = convert_hpxml_and_parse(hpxml_dir / "version_change.xml")
    assert root.attrib["schemaVersion"] == "5.0"


def test_not_present():
    root = convert_hpxml_and_parse(hpxml_dir / "not_present.xml")

    for i in (0, 1):
        fnd = root.Building[0].BuildingDetails.Enclosure.Foundations.Foundation[i]
        assert fnd.FoundationType.BellyAndWing.BellyWrapCondition == "not present"

    roof = root.Building[0].BuildingDetails.Enclosure.Roofs.Roof
    roof_ins_mat = roof.Insulation.Layer.InsulationMaterial
    assert hasattr(roof_ins_mat, "NotPresent")

    for i in (0, 1):
        wall = root.Building[0].BuildingDetails.Enclosure.Walls.Wall[i]
        assert wall.Siding == "not present"
        assert wall.InteriorFinish.Type == "not present"

    for i in (0, 1, 2):
        floor = root.Building[0].BuildingDetails.Enclosure.Floors.Floor[i]
        assert floor.FloorCovering == "not present"
        if i > 0:
            floor_ins_mat = floor.Insulation.Layer.InsulationMaterial
            assert hasattr(floor_ins_mat, "NotPresent")

    for i in (0, 1, 2):
        window = root.Building[0].BuildingDetails.Enclosure.Windows.Window[i]
        skylight = root.Building[0].BuildingDetails.Enclosure.Skylights.Skylight[i]
        if i == 0:
            assert window.ExteriorShading.Type == "not present"
            assert skylight.ExteriorShading.Type == "not present"
        elif i == 1:
            assert window.InteriorShading.Type != "not present"
            assert skylight.InteriorShading.Type != "not present"
        else:
            assert not hasattr(window, "Type")
            assert not hasattr(skylight, "Type")

    for i in (0, 1):
        pool = root.Building[0].BuildingDetails.Pools.Pool[i]
        spa = root.Building[0].BuildingDetails.Spas.PermanentSpa[i]
        assert pool.Type == "not present"
        assert pool.Pumps.Pump[0].Type == "not present"
        assert pool.Pumps.Pump[1].Type == "not present"
        assert pool.Cleaner.Type == "not present"
        assert pool.Heater.Type == "not present"
        assert spa.Type == "not present"
        assert spa.Pumps.Pump[0].Type == "not present"
        assert spa.Pumps.Pump[1].Type == "not present"
        assert spa.Cleaner.Type == "not present"
        assert spa.Heater.Type == "not present"


def test_refrigerator_uncategorized():
    root = convert_hpxml_and_parse(hpxml_dir / "refrigerator_uncategorized.xml")

    for i in (0, 1, 2, 3):
        fridge = root.Building[0].BuildingDetails.Appliances.Refrigerator[i]
        if i in (0, 2):
            assert fridge.Type == "other"
        elif i == 1:
            assert not hasattr(fridge, "Type")
        elif i == 3:
            assert fridge.Type != "other"


def test_solar_tube():
    root = convert_hpxml_and_parse(hpxml_dir / "solar_tube.xml")

    for i in (0, 1, 2):
        skylight = root.Building[0].BuildingDetails.Enclosure.Skylights.Skylight[i]
        if i == 1:
            assert skylight.SkylightType == "tubular"
        else:
            assert not hasattr(skylight, "SkylightType")


def test_mismatch_version():
    f_out = io.BytesIO()
    with pytest.raises(
        exc.HpxmlTranslationError,
        match=r"convert_hpxml4_to_5 must have valid target version of 5\.x",
    ):
        convert_hpxml4_to_5(hpxml_dir / "version_change.xml", f_out, "2.0")
