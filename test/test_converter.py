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


def test_enclosure_foundation_walls():
    root = convert_hpxml_and_parse(hpxml_dir / 'enclosure_foundation_walls.xml')

    fw1 = root.Building.BuildingDetails.Enclosure.FoundationWalls.FoundationWall[0]
    assert fw1.getparent().getparent().Foundations.Foundation.AttachedToFoundationWall[0].attrib['idref']\
        == 'foundationwall-1'
    assert fw1.InteriorAdjacentTo == 'basement - unconditioned'
    assert fw1.Type == 'concrete block'
    assert fw1.Length == 120
    assert fw1.Height == 8
    assert fw1.Area == 960
    assert fw1.Thickness == 4
    assert fw1.DepthBelowGrade == 6
    assert not hasattr(fw1, 'AdjacentTo')
    assert fw1.Insulation.InsulationGrade == 3
    assert fw1.Insulation.InsulationCondition == 'good'
    assert fw1.Insulation.AssemblyEffectiveRValue == 5.0
    assert not hasattr(fw1.Insulation, 'Location')

    fw2 = root.Building.BuildingDetails.Enclosure.FoundationWalls.FoundationWall[1]
    assert fw2.getparent().getparent().Foundations.Foundation.AttachedToFoundationWall[1].attrib['idref']\
        == 'foundationwall-2'
    assert not hasattr(fw2, 'ExteriorAdjacentTo')
    assert not hasattr(fw2, 'InteriorAdjacentTo')
    assert fw2.Type == 'concrete block'
    assert fw2.Length == 60
    assert fw2.Height == 8
    assert fw2.Area == 480
    assert fw2.Thickness == 7
    assert fw2.DepthBelowGrade == 8
    assert not hasattr(fw2, 'AdjacentTo')
    assert fw2.Insulation.InsulationGrade == 1
    assert fw2.Insulation.InsulationCondition == 'poor'
    assert not hasattr(fw2.Insulation, 'Location')
    assert fw2.Insulation.Layer[0].InstallationType == 'continuous'
    assert fw2.Insulation.Layer[0].InsulationMaterial.Batt == 'fiberglass'
    assert fw2.Insulation.Layer[0].NominalRValue == 8.9
    assert fw2.Insulation.Layer[0].Thickness == 1.5
    assert fw2.Insulation.Layer[1].InstallationType == 'cavity'
    assert fw2.Insulation.Layer[1].InsulationMaterial.Rigid == 'eps'
    assert fw2.Insulation.Layer[1].NominalRValue == 15.0
    assert fw2.Insulation.Layer[1].Thickness == 3.0


def test_frame_floors():
    root = convert_hpxml_and_parse(hpxml_dir / 'enclosure_frame_floors.xml')

    ff1 = root.Building.BuildingDetails.Enclosure.FrameFloors.FrameFloor[0]
    assert ff1.getparent().getparent().Foundations.Foundation.AttachedToFrameFloor[0].attrib['idref'] == 'framefloor-1'
    assert ff1.FloorCovering == 'hardwood'
    assert ff1.Area == 1350.0
    assert ff1.Insulation.AssemblyEffectiveRValue == 39.3
    assert not hasattr(ff1.Insulation, 'InsulationLocation')
    assert not hasattr(ff1.Insulation, 'Layer')

    ff2 = root.Building.BuildingDetails.Enclosure.FrameFloors.FrameFloor[1]
    assert ff2.getparent().getparent().Foundations.Foundation.AttachedToFrameFloor[1].attrib['idref'] == 'framefloor-2'
    assert ff2.FloorCovering == 'carpet'
    assert ff2.Area == 1350.0
    assert ff2.Insulation.InsulationGrade == 1
    assert ff2.Insulation.InsulationCondition == 'poor'
    assert ff2.Insulation.Layer[0].InstallationType == 'continuous - exterior'
    assert ff2.Insulation.Layer[0].NominalRValue == 30.0
    assert ff2.Insulation.Layer[0].Thickness == 1.5
    assert ff2.Insulation.Layer[1].InstallationType == 'continuous - exterior'
    assert ff2.Insulation.Layer[1].NominalRValue == 8.0
    assert ff2.Insulation.Layer[1].Thickness == 0.25
    assert not hasattr(ff2.Insulation, 'InsulationLocation')


def test_slabs():
    root = convert_hpxml_and_parse(hpxml_dir / 'enclosure_slabs.xml')

    slab1 = root.Building.BuildingDetails.Enclosure.Slabs.Slab[0]
    assert slab1.getparent().getparent().Foundations.Foundation.AttachedToSlab.attrib['idref'] == 'slab-1'
    assert slab1.Area == 1350.0
    assert slab1.Thickness == 4.0
    assert slab1.ExposedPerimeter == 150.0
    assert slab1.PerimeterInsulationDepth == 0.0
    assert slab1.UnderSlabInsulationWidth == 0.0
    assert slab1.PerimeterInsulation.Layer.NominalRValue == 0.0
    assert slab1.UnderSlabInsulation.Layer.NominalRValue == 0.0
    assert slab1.extension.CarpetFraction == 0.0
    assert slab1.extension.CarpetRValue == 0.0
