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
    assert enclosure.FrameFloors.FrameFloor[0].Area == 1500.0
    assert enclosure.FrameFloors.FrameFloor[0].Insulation.InsulationGrade == 1
    assert enclosure.FrameFloors.FrameFloor[0].Insulation.InsulationCondition == 'poor'
    assert enclosure.FrameFloors.FrameFloor[0].Insulation.AssemblyEffectiveRValue == 5.5

    attic2 = root.Building.BuildingDetails.Enclosure.Attics.Attic[1]
    assert attic2.AtticType.Attic.extension.Vented == 'unknown'  # venting unknown attic

    attic3 = root.Building.BuildingDetails.Enclosure.Attics.Attic[2]
    assert attic3.AtticType.Attic.Vented  # vented attic

    attic4 = root.Building.BuildingDetails.Enclosure.Attics.Attic[3]
    assert hasattr(attic4.AtticType, 'FlatRoof')

    attic5 = root.Building.BuildingDetails.Enclosure.Attics.Attic[4]
    assert hasattr(attic5.AtticType, 'CathedralCeiling')

    attic6 = root.Building.BuildingDetails.Enclosure.Attics.Attic[5]
    assert attic6.AtticType.Attic.CapeCod

    attic7 = root.Building.BuildingDetails.Enclosure.Attics.Attic[6]
    assert hasattr(attic7.AtticType, 'Other')


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
    assert fw2.Insulation.Layer[0].InstallationType == 'continuous - exterior'
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


def test_walls():
    root = convert_hpxml_and_parse(hpxml_dir / 'enclosure_walls.xml')

    wall1 = root.Building.BuildingDetails.Enclosure.Walls.Wall[0]
    assert wall1.ExteriorAdjacentTo == 'outside'
    assert wall1.InteriorAdjacentTo == 'living space'
    assert hasattr(wall1.WallType, 'WoodStud')
    assert wall1.Thickness == 0.5
    assert wall1.Area == 750
    assert wall1.Azimuth == 0
    assert wall1.Siding == 'wood siding'
    assert wall1.SolarAbsorptance == 0.6
    assert wall1.Emittance == 0.7
    assert wall1.Insulation.InsulationGrade == 1
    assert wall1.Insulation.InsulationCondition == 'good'
    assert not hasattr(wall1.Insulation, 'InsulationLocation')
    assert wall1.Insulation.Layer[0].InstallationType == 'continuous - exterior'
    assert wall1.Insulation.Layer[0].InsulationMaterial.Rigid == 'xps'
    assert wall1.Insulation.Layer[0].NominalRValue == 5.5
    assert wall1.Insulation.Layer[0].Thickness == 1.5
    assert wall1.Insulation.Layer[1].InstallationType == 'cavity'
    assert wall1.Insulation.Layer[1].InsulationMaterial.Batt == 'fiberglass'
    assert wall1.Insulation.Layer[1].NominalRValue == 12.0
    assert wall1.Insulation.Layer[1].Thickness == 3.5


def test_windows():
    root = convert_hpxml_and_parse(hpxml_dir / 'enclosure_windows_skylights.xml')

    win1 = root.Building.BuildingDetails.Enclosure.Windows.Window[0]
    assert win1.Area == 108.0
    assert win1.Azimuth == 0
    assert win1.UFactor == 0.33
    assert win1.SHGC == 0.45
    assert win1.NFRCCertified
    assert win1.VisibleTransmittance == 0.9
    assert win1.ExteriorShading[0].Type == 'solar screens'
    assert win1.ExteriorShading[1].Type == 'evergreen tree'
    assert win1.InteriorShading.Type == 'light shades'
    assert win1.InteriorShading.SummerShadingCoefficient == 0.7
    assert win1.InteriorShading.WinterShadingCoefficient == 0.7
    assert win1.MoveableInsulation.RValue == 5.5
    assert win1.AttachedToWall.attrib['idref'] == 'wall-1'
    assert not hasattr(win1, 'Treatments')
    assert not hasattr(win1, 'InteriorShadingFactor')
    assert not hasattr(win1, 'MovableInsulationRValue')

    win2 = root.Building.BuildingDetails.Enclosure.Windows.Window[1]
    assert win2.GlassLayers == 'single-pane'
    assert win2.StormWindow.GlassType == 'low-e'
    assert win2.ExteriorShading[0].Type == 'solar film'

    win3 = root.Building.BuildingDetails.Enclosure.Windows.Window[2]
    assert hasattr(win3, 'WindowFilm')

    skylight1 = root.Building.BuildingDetails.Enclosure.Skylights.Skylight[0]
    assert skylight1.Area == 20.0
    assert skylight1.UFactor == 0.25
    assert skylight1.SHGC == 0.60
    assert skylight1.ExteriorShading[0].Type == 'solar screens'
    assert skylight1.ExteriorShading[1].Type == 'building'
    assert skylight1.InteriorShading.Type == 'dark shades'
    assert skylight1.InteriorShading.SummerShadingCoefficient == 0.65
    assert skylight1.InteriorShading.WinterShadingCoefficient == 0.65
    assert skylight1.MoveableInsulation.RValue == 3.5
    assert skylight1.Pitch == 6.0
    assert not hasattr(skylight1, 'Treatments')
    assert not hasattr(skylight1, 'InteriorShadingFactor')
    assert not hasattr(skylight1, 'MovableInsulationRValue')


def test_standard_locations():
    root = convert_hpxml_and_parse(hpxml_dir / 'standard_locations.xml')

    wall1 = root.Building[0].BuildingDetails.Enclosure.Walls.Wall[0]
    assert wall1.ExteriorAdjacentTo == 'outside'
    assert wall1.InteriorAdjacentTo == 'living space'
    wall2 = root.Building[0].BuildingDetails.Enclosure.Walls.Wall[1]
    assert wall2.ExteriorAdjacentTo == 'ground'
    assert wall2.InteriorAdjacentTo == 'basement - unconditioned'
    wall3 = root.Building[0].BuildingDetails.Enclosure.Walls.Wall[2]
    assert wall3.ExteriorAdjacentTo == 'other housing unit'
    assert wall3.InteriorAdjacentTo == 'crawlspace'
    wall4 = root.Building[0].BuildingDetails.Enclosure.Walls.Wall[3]
    assert wall4.ExteriorAdjacentTo == 'garage'
    assert wall4.InteriorAdjacentTo == 'other'

    hvac_dist1 = root.Building[0].BuildingDetails.Systems.HVAC.HVACDistribution[0]
    assert hvac_dist1.DistributionSystemType.AirDistribution.AirDistributionType == 'regular velocity'
    duct1 = hvac_dist1.DistributionSystemType.AirDistribution.Ducts[0]
    assert duct1.DuctType == 'supply'
    assert duct1.DuctLocation == 'attic - unconditioned'
    duct2 = hvac_dist1.DistributionSystemType.AirDistribution.Ducts[1]
    assert duct2.DuctType == 'supply'
    assert duct2.DuctLocation == 'basement - unconditioned'
    duct3 = hvac_dist1.DistributionSystemType.AirDistribution.Ducts[2]
    assert duct3.DuctType == 'supply'
    assert duct3.DuctLocation == 'living space'
    duct4 = hvac_dist1.DistributionSystemType.AirDistribution.Ducts[3]
    assert duct4.DuctType == 'return'
    assert duct4.DuctLocation == 'crawlspace - unvented'
    duct5 = hvac_dist1.DistributionSystemType.AirDistribution.Ducts[4]
    assert duct5.DuctType == 'return'
    assert duct5.DuctLocation == 'crawlspace - vented'
    duct6 = hvac_dist1.DistributionSystemType.AirDistribution.Ducts[5]
    assert duct6.DuctType == 'return'
    assert duct6.DuctLocation == 'unconditioned space'

    wall5 = root.Building[1].BuildingDetails.Enclosure.Walls.Wall[0]
    assert wall5.ExteriorAdjacentTo == 'outside'
    assert wall5.InteriorAdjacentTo == 'living space'
    wall6 = root.Building[1].BuildingDetails.Enclosure.Walls.Wall[1]
    assert wall6.ExteriorAdjacentTo == 'ground'
    assert wall6.InteriorAdjacentTo == 'basement - unconditioned'
    wall7 = root.Building[1].BuildingDetails.Enclosure.Walls.Wall[2]
    assert wall7.ExteriorAdjacentTo == 'other housing unit'
    assert wall7.InteriorAdjacentTo == 'crawlspace'
    wall8 = root.Building[1].BuildingDetails.Enclosure.Walls.Wall[3]
    assert wall8.ExteriorAdjacentTo == 'garage'
    assert wall8.InteriorAdjacentTo == 'other'

    hvac_dist2 = root.Building[1].BuildingDetails.Systems.HVAC.HVACDistribution[0]
    assert hvac_dist2.DistributionSystemType.AirDistribution.AirDistributionType == 'regular velocity'
    duct7 = hvac_dist2.DistributionSystemType.AirDistribution.Ducts[0]
    assert duct7.DuctType == 'supply'
    assert duct7.DuctLocation == 'attic - unconditioned'
    duct8 = hvac_dist2.DistributionSystemType.AirDistribution.Ducts[1]
    assert duct8.DuctType == 'supply'
    assert duct8.DuctLocation == 'basement - unconditioned'
    duct9 = hvac_dist2.DistributionSystemType.AirDistribution.Ducts[2]
    assert duct9.DuctType == 'supply'
    assert duct9.DuctLocation == 'living space'
    duct10 = hvac_dist2.DistributionSystemType.AirDistribution.Ducts[3]
    assert duct10.DuctType == 'return'
    assert duct10.DuctLocation == 'crawlspace - unvented'
    duct11 = hvac_dist2.DistributionSystemType.AirDistribution.Ducts[4]
    assert duct11.DuctType == 'return'
    assert duct11.DuctLocation == 'crawlspace - vented'
    duct12 = hvac_dist2.DistributionSystemType.AirDistribution.Ducts[5]
    assert duct12.DuctType == 'return'
    assert duct12.DuctLocation == 'unconditioned space'

    # Make sure we're not unintentionally changing elements that shouldn't be
    assert root.XMLTransactionHeaderInformation.XMLGeneratedBy == 'unconditioned basement'


def test_lighting():
    root = convert_hpxml_and_parse(hpxml_dir / 'lighting.xml')

    ltg = root.Building.BuildingDetails.Lighting
    assert not hasattr(ltg, 'LightingFractions')

    ltg_grp1 = ltg.LightingGroup[0]
    assert ltg_grp1.FractionofUnitsInLocation == 0.5
    assert hasattr(ltg_grp1.LightingType, 'Incandescent')

    ltg_grp2 = ltg.LightingGroup[1]
    assert ltg_grp2.FractionofUnitsInLocation == 0.1
    assert hasattr(ltg_grp2.LightingType, 'CompactFluorescent')

    ltg_grp3 = ltg.LightingGroup[2]
    assert ltg_grp3.FractionofUnitsInLocation == 0.1
    assert hasattr(ltg_grp3.LightingType, 'FluorescentTube')

    ltg_grp4 = ltg.LightingGroup[3]
    assert ltg_grp4.FractionofUnitsInLocation == 0.3
    assert hasattr(ltg_grp4.LightingType, 'LightEmittingDiode')
