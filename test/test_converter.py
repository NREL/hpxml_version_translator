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


def test_enclosure_attics():
    root = convert_hpxml_and_parse(hpxml_dir / 'enclosure_attics_and_roofs.xml')

    attic1 = root.Building.BuildingDetails.Enclosure.Attics.Attic[0]
    enclosure = attic1.getparent().getparent()
    assert not attic1.AtticType.Attic.Vented  # unvented attic
    assert attic1.AttachedToRoof.attrib['idref'] == 'roof-1'
    assert not hasattr(enclosure, 'AtticAndRoof')
    assert not hasattr(enclosure, 'ExteriorAdjacentTo')
    assert enclosure.Walls.Wall[0].AtticWallType == 'knee wall'
    assert enclosure.Roofs.Roof[0].Rafters.Size == '2x4'
    assert enclosure.Roofs.Roof[0].Rafters.Material == 'wood'
    assert enclosure.Roofs.Roof[0].Insulation.InsulationGrade == 3
    assert enclosure.Roofs.Roof[0].Insulation.InsulationCondition == 'good'
    assert enclosure.Roofs.Roof[0].Insulation.Layer.InstallationType == 'cavity'
    assert enclosure.Roofs.Roof[0].Insulation.Layer.NominalRValue == 7.5
    assert enclosure.FrameFloors.FrameFloor[0].InteriorAdjacentTo == 'attic'
    assert enclosure.FrameFloors.FrameFloor[0].Insulation.InsulationGrade == 1
    assert enclosure.FrameFloors.FrameFloor[0].Insulation.InsulationCondition == 'poor'
    assert enclosure.FrameFloors.FrameFloor[0].Insulation.AssemblyEffectiveRValue == 5.5

    attic2 = root.Building.BuildingDetails.Enclosure.Attics.Attic[1]
    assert attic2.AtticType.Attic.extension.Vented == 'unknown'  # venting unknown attic


def test_enclosure_roofs():
    root = convert_hpxml_and_parse(hpxml_dir / 'enclosure_attics_and_roofs.xml')

    roof1 = root.Building.BuildingDetails.Enclosure.Roofs.Roof[0]
    enclosure = roof1.getparent().getparent()
    assert roof1.Area == 1118.5
    assert roof1.RoofType == 'shingles'
    assert roof1.RoofColor == 'dark'
    assert roof1.SolarAbsorptance == 0.7
    assert roof1.Emittance == 0.9
    assert roof1.Pitch == 6.0
    assert not hasattr(roof1, 'RoofArea')
    assert not hasattr(enclosure, 'AtticAndRoof')


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
