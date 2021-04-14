from lxml import objectify
import pathlib
import tempfile

from hpxml_version_translator.converter import convert_hpxml2_to_3


hpxml_dir = pathlib.Path(__file__).resolve().parent / 'hpxml_files'


def convert_hpxml_and_parse(input_filename):
    with tempfile.TemporaryFile('w+b') as f_out:
        convert_hpxml2_to_3(input_filename, f_out)
        f_out.seek(0)
        root = objectify.parse(f_out).getroot()
    return root


def test_version_change():
    root = convert_hpxml_and_parse(hpxml_dir / 'version_change.xml')
    assert root.attrib['schemaVersion'] == '3.0'


def test_project_ids():
    root = convert_hpxml_and_parse(hpxml_dir / 'project_ids.xml')
    root.Project.PreBuildingID == 'bldg1'
    root.Project.PostBuildingID == 'bldg2'
    # TODO: test project ids failures


def test_green_building_verification():
    root = convert_hpxml_and_parse(hpxml_dir / 'green_building_verification.xml')

    gbv0 = root.Building[0].BuildingDetails.GreenBuildingVerifications.GreenBuildingVerification[0]
    assert gbv0.Type == 'Home Energy Score'
    assert gbv0.Body == 'US DOE'
    assert gbv0.Year == 2021
    assert gbv0.Metric == 5
    assert gbv0.extension.asdf == 'jkl'

    gbv1 = root.Building[0].BuildingDetails.GreenBuildingVerifications.GreenBuildingVerification[1]
    assert gbv1.Type == 'HERS Index Score'
    assert gbv1.Body == 'RESNET'
    assert not hasattr(gbv1, 'Year')
    assert gbv1.Metric == 62

    gbv3 = root.Building[0].BuildingDetails.GreenBuildingVerifications.GreenBuildingVerification[2]
    assert gbv3.Type == 'other'
    assert gbv3.Body == 'other'
    assert gbv3.OtherType == 'My own special scoring system'
    assert gbv3.Metric == 11

    gbv4 = root.Building[1].BuildingDetails.GreenBuildingVerifications.GreenBuildingVerification[0]
    assert gbv4.Type == 'Home Performance with ENERGY STAR'
    assert gbv4.Body == 'local program'
    assert gbv4.URL == 'http://energy.gov'
    assert gbv4.Year == 2020

    gbv5 = root.Building[1].BuildingDetails.GreenBuildingVerifications.GreenBuildingVerification[2]
    assert gbv5.Type == 'ENERGY STAR Certified Homes'
    assert gbv5.Version == 3.1

    gbv6 = root.Building[1].BuildingDetails.GreenBuildingVerifications.GreenBuildingVerification[1]
    assert gbv6.Type == 'LEED For Homes'
    assert gbv6.Body == 'USGBC'
    assert gbv6.Rating == 'Gold'
    assert gbv6.URL == 'http://usgbc.org'
    assert gbv6.Year == 2019


def test_clothes_dryer():
    root = convert_hpxml_and_parse(hpxml_dir / 'clothes_dryer.xml')

    dryer1 = root.Building.BuildingDetails.Appliances.ClothesDryer[0]
    assert dryer1.Type == 'dryer'
    assert dryer1.Location == 'laundry room'
    assert dryer1.FuelType == 'natural gas'
    assert dryer1.EnergyFactor == 2.5
    assert dryer1.ControlType == 'timer'
    assert not hasattr(dryer1, 'EfficiencyFactor')

    dryer2 = root.Building.BuildingDetails.Appliances.ClothesDryer[1]
    assert dryer2.Type == 'all-in-one combination washer/dryer'
    assert dryer2.Location == 'basement'
    assert dryer2.FuelType == 'electricity'
    assert dryer2.EnergyFactor == 5.0
    assert dryer2.ControlType == 'temperature'
    assert not hasattr(dryer2, 'EfficiencyFactor')


def test_inconsistencies():
    root = convert_hpxml_and_parse(hpxml_dir / 'inconsistencies.xml')

    ws = root.Building.BuildingDetails.ClimateandRiskZones.WeatherStation[0]
    assert ws.SystemIdentifier.attrib['id'] == 'weather-station-1'

    clgsys = root.Building.BuildingDetails.Systems.HVAC.HVACPlant.CoolingSystem[0]
    assert clgsys.CoolingSystemType.text == 'central air conditioner'

    htpump = root.Building.BuildingDetails.Systems.HVAC.HVACPlant.HeatPump[0]
    assert htpump.AnnualCoolingEfficiency.Units == 'SEER'
    assert htpump.AnnualCoolingEfficiency.Value == 13.0
    assert htpump.AnnualHeatingEfficiency.Units == 'HSPF'
    assert htpump.AnnualHeatingEfficiency.Value == 7.7
    assert htpump.BackupAnnualHeatingEfficiency.Units == 'AFUE'
    assert htpump.BackupAnnualHeatingEfficiency.Value == 0.98

    measure = root.Project.ProjectDetails.Measures.Measure[0]
    assert measure.InstalledComponents.InstalledComponent.attrib['id'] == 'installed-component-1'
    assert not hasattr(measure, 'InstalledComponent')
    assert measure.InstalledComponents.getnext() == measure.extension

    fw1 = root.Building.BuildingDetails.Enclosure.FoundationWalls.FoundationWall[0]
    assert fw1.Type == 'concrete block'
    assert fw1.Length == 120
    assert fw1.Height == 8
    assert fw1.Area == 960
    assert fw1.Thickness == 4
    assert fw1.DepthBelowGrade == 6
    assert fw1.Insulation.InsulationGrade == 3
    assert fw1.Insulation.InsulationCondition == 'good'
    assert fw1.Insulation.AssemblyEffectiveRValue == 5.0

    fw2 = root.Building.BuildingDetails.Enclosure.FoundationWalls.FoundationWall[1]
    assert fw2.Type == 'concrete block'
    assert fw2.Length == 60
    assert fw2.Height == 8
    assert fw2.Area == 480
    assert fw2.Thickness == 7
    assert fw2.DepthBelowGrade == 8
    assert fw2.Insulation.InsulationGrade == 1
    assert fw2.Insulation.InsulationCondition == 'poor'
    # FIXME: should InstallationType be either 'continuous - exterior' or 'continuous - interior'?
    assert fw2.Insulation.Layer.InstallationType == 'continuous'
    assert fw2.Insulation.Layer.NominalRValue == 8.9
    assert fw2.Insulation.Layer.extension.DistanceToTopOfInsulation == 0.0
    assert fw2.Insulation.Layer.extension.DistanceToBottomOfInsulation == 8.0
