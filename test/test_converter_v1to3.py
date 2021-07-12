from lxml import objectify
import pathlib
import tempfile

from hpxml_version_translator.converter import convert_hpxml_to_3


hpxml_dir = pathlib.Path(__file__).resolve().parent / 'hpxml_v1_files'


def convert_hpxml_and_parse(input_filename):
    with tempfile.NamedTemporaryFile('w+b') as f_out:
        convert_hpxml_to_3(input_filename, f_out)
        f_out.seek(0)
        root = objectify.parse(f_out).getroot()
    return root


def test_version_change():
    root = convert_hpxml_and_parse(hpxml_dir / 'version_change.xml')
    assert root.attrib['schemaVersion'] == '3.0'


def test_water_heater_caz():
    root = convert_hpxml_and_parse(hpxml_dir / 'water_heater_caz.xml')

    whs1 = root.Building.BuildingDetails.Systems.WaterHeating.WaterHeatingSystem[0]
    assert whs1.AttachedToCAZ.attrib['idref'] == 'water-heater-caz'

    whs2 = root.Building.BuildingDetails.Systems.WaterHeating.WaterHeatingSystem[1]
    assert whs2.AttachedToCAZ.attrib['idref'] == 'water-heater-caz-2'


def test_solar_thermal():
    root = convert_hpxml_and_parse(hpxml_dir / 'solar_thermal.xml')

    sts1 = root.Building.BuildingDetails.Systems.SolarThermal.SolarThermalSystem[0]
    assert not hasattr(sts1, 'CollectorLoopType')
    assert sts1.CollectorType == 'integrated collector storage'

    sts2 = root.Building.BuildingDetails.Systems.SolarThermal.SolarThermalSystem[1]
    assert not hasattr(sts2, 'CollectorLoopType')
    assert sts2.CollectorType == 'single glazing black'
