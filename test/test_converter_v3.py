import io
from lxml import objectify
import pathlib
import pytest
import tempfile

from hpxml_version_translator.converter import (
    convert_hpxml3_to_4,
    convert_hpxml_to_version,
)
from hpxml_version_translator import exceptions as exc


hpxml_dir = pathlib.Path(__file__).resolve().parent / "hpxml_v3_files"


def convert_hpxml_and_parse(input_filename, version="4.0"):
    with tempfile.NamedTemporaryFile("w+b") as f_out:
        convert_hpxml_to_version(version, input_filename, f_out)
        f_out.seek(0)
        root = objectify.parse(f_out).getroot()
    return root


def test_version_change_to_4():
    root = convert_hpxml_and_parse(hpxml_dir / "version_change.xml")
    assert root.attrib["schemaVersion"] == "4.0"


def test_enclosure_foundation():
    root = convert_hpxml_and_parse(hpxml_dir / "enclosure_foundation.xml")

    for i in (0, 1):
        fw1 = root.Building[i].BuildingDetails.Enclosure.FoundationWalls.FoundationWall[
            0
        ]
        assert not hasattr(fw1, "DistanceToTopOfInsulation")
        assert not hasattr(fw1, "DistanceToBottomOfInsulation")

        fw2 = root.Building[i].BuildingDetails.Enclosure.FoundationWalls.FoundationWall[
            1
        ]
        assert not hasattr(fw2, "DistanceToTopOfInsulation")
        assert not hasattr(fw2, "DistanceToBottomOfInsulation")
        assert fw2.Insulation.Layer[0].DistanceToTopOfInsulation == 1.0
        assert fw2.Insulation.Layer[1].DistanceToTopOfInsulation == 1.0
        assert fw2.Insulation.Layer[0].DistanceToBottomOfInsulation == 5.0
        assert fw2.Insulation.Layer[1].DistanceToBottomOfInsulation == 5.0

        sl1 = root.Building[i].BuildingDetails.Enclosure.Slabs.Slab[0]
        assert not hasattr(fw1, "PerimeterInsulationDepth")
        assert not hasattr(fw1, "UnderSlabInsulationWidth")
        assert not hasattr(fw1, "UnderSlabInsulationSpansSlab")
        assert sl1.PerimeterInsulation.Layer[0].InsulationDepth == 2.0
        assert sl1.UnderSlabInsulation.Layer[0].InsulationWidth == 1.0
        assert not sl1.UnderSlabInsulation.Layer[0].InsulationSpansEntireSlab


def test_battery():
    root = convert_hpxml_and_parse(hpxml_dir / "battery.xml")

    b1 = root.Building[0].BuildingDetails.Systems.Batteries.Battery[0]
    assert b1.NominalCapacity.Units == "Ah"
    assert b1.NominalCapacity.Value == 1000
    assert b1.UsableCapacity.Units == "Ah"
    assert b1.UsableCapacity.Value == 800

    b2 = root.Building[0].BuildingDetails.Systems.Batteries.Battery[1]
    assert b2.NominalCapacity.Units == "Ah"
    assert b2.NominalCapacity.Value == 2000
    assert b2.UsableCapacity.Units == "Ah"
    assert b2.UsableCapacity.Value == 1600


def test_mismatch_version():
    f_out = io.BytesIO()
    with pytest.raises(
        exc.HpxmlTranslationError,
        match=r"convert_hpxml3_to_4 must have valid target version of 4\.x",
    ):
        convert_hpxml3_to_4(hpxml_dir / "version_change.xml", f_out, "2.0")
