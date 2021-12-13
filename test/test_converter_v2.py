import io
from lxml import objectify
import pathlib
import pytest
import tempfile

from hpxml_version_translator.converter import (
    convert_hpxml_to_3,
    convert_hpxml_to_version,
    convert_hpxml2_to_3,
)
from hpxml_version_translator import exceptions as exc


hpxml_dir = pathlib.Path(__file__).resolve().parent / "hpxml_v2_files"


def convert_hpxml_and_parse(input_filename, version="3.0"):
    with tempfile.NamedTemporaryFile("w+b") as f_out:
        convert_hpxml_to_version(version, input_filename, f_out)
        f_out.seek(0)
        root = objectify.parse(f_out).getroot()
    return root


def test_version_change():
    root = convert_hpxml_and_parse(hpxml_dir / "version_change.xml")
    assert root.attrib["schemaVersion"] == "3.0"


def test_attempt_to_change_to_same_version():
    with pytest.raises(
        exc.HpxmlTranslationError,
        match=r"HPXML version requested is 2\.3 but input file major version is 2",
    ):
        convert_hpxml_and_parse(hpxml_dir / "version_change.xml", version="2.3")


def test_attempt_to_use_nonexistent_version():
    with pytest.raises(
        exc.HpxmlTranslationError,
        match=r"HPXML version 5\.0 is not valid\. Must be one of",
    ):
        convert_hpxml_and_parse(hpxml_dir / "version_change.xml", version="5.0")


def test_convert_hpxml_to_3():
    with tempfile.NamedTemporaryFile("w+b") as f_out:
        with pytest.deprecated_call():
            convert_hpxml_to_3(hpxml_dir / "version_change.xml", f_out)
        f_out.seek(0)
        root = objectify.parse(f_out).getroot()
    assert root.attrib["schemaVersion"] == "3.0"


def test_mismatch_version():
    f_out = io.BytesIO()
    with pytest.raises(
        exc.HpxmlTranslationError,
        match=r"convert_hpxml2_to_3 must have valid target version of 3\.x",
    ):
        convert_hpxml2_to_3(hpxml_dir / "version_change.xml", f_out, "2.0")


def test_project_ids():
    root = convert_hpxml_and_parse(hpxml_dir / "project_ids.xml")
    assert root.Project.PreBuildingID.attrib["id"] == "bldg1"
    assert root.Project.PostBuildingID.attrib["id"] == "bldg2"


def test_project_ids2():
    root = convert_hpxml_and_parse(hpxml_dir / "project_ids2.xml")
    assert root.Project.PreBuildingID.attrib["id"] == "bldg1"
    assert root.Project.PostBuildingID.attrib["id"] == "bldg2"


def test_project_ids_fail1():
    with pytest.raises(
        exc.HpxmlTranslationError,
        match=r"Project\[\d\] has more than one reference.*audit",
    ):
        convert_hpxml_and_parse(hpxml_dir / "project_ids_fail1.xml")


def test_project_ids_fail2():
    with pytest.raises(
        exc.HpxmlTranslationError, match=r"Project\[\d\] has no references.*audit"
    ):
        convert_hpxml_and_parse(hpxml_dir / "project_ids_fail2.xml")


def test_project_ids_fail3():
    with pytest.raises(
        exc.HpxmlTranslationError,
        match=r"Project\[\d\] has more than one reference.*post retrofit",
    ):
        convert_hpxml_and_parse(hpxml_dir / "project_ids_fail3.xml")


def test_project_ids_fail4():
    with pytest.raises(
        exc.HpxmlTranslationError,
        match=r"Project\[\d\] has no references.*post retrofit",
    ):
        convert_hpxml_and_parse(hpxml_dir / "project_ids_fail4.xml")


def test_green_building_verification():
    root = convert_hpxml_and_parse(hpxml_dir / "green_building_verification.xml")

    gbv0 = root.Building[
        0
    ].BuildingDetails.GreenBuildingVerifications.GreenBuildingVerification[0]
    assert gbv0.Type == "Home Energy Score"
    assert gbv0.Body == "US DOE"
    assert gbv0.Year == 2021
    assert gbv0.Metric == 5
    assert gbv0.extension.asdf == "jkl"

    gbv1 = root.Building[
        0
    ].BuildingDetails.GreenBuildingVerifications.GreenBuildingVerification[1]
    assert gbv1.Type == "HERS Index Score"
    assert gbv1.Body == "RESNET"
    assert not hasattr(gbv1, "Year")
    assert gbv1.Metric == 62

    gbv3 = root.Building[
        0
    ].BuildingDetails.GreenBuildingVerifications.GreenBuildingVerification[2]
    assert gbv3.Type == "other"
    assert gbv3.Body == "other"
    assert gbv3.OtherType == "My own special scoring system"
    assert gbv3.Metric == 11

    gbv4 = root.Building[
        1
    ].BuildingDetails.GreenBuildingVerifications.GreenBuildingVerification[0]
    assert gbv4.Type == "Home Performance with ENERGY STAR"
    assert gbv4.Body == "local program"
    assert gbv4.URL == "http://energy.gov"
    assert gbv4.Year == 2020

    gbv5 = root.Building[
        1
    ].BuildingDetails.GreenBuildingVerifications.GreenBuildingVerification[2]
    assert gbv5.Type == "ENERGY STAR Certified Homes"
    assert gbv5.Version == 3.1

    gbv6 = root.Building[
        1
    ].BuildingDetails.GreenBuildingVerifications.GreenBuildingVerification[1]
    assert gbv6.Type == "LEED For Homes"
    assert gbv6.Body == "USGBC"
    assert gbv6.Rating == "Gold"
    assert gbv6.URL == "http://usgbc.org"
    assert gbv6.Year == 2019


def test_inconsistencies():
    root = convert_hpxml_and_parse(hpxml_dir / "inconsistencies.xml")

    ws = root.Building.BuildingDetails.ClimateandRiskZones.WeatherStation[0]
    assert ws.SystemIdentifier.attrib["id"] == "weather-station-1"

    clgsys = root.Building.BuildingDetails.Systems.HVAC.HVACPlant.CoolingSystem[0]
    assert clgsys.CoolingSystemType.text == "central air conditioner"

    htpump = root.Building.BuildingDetails.Systems.HVAC.HVACPlant.HeatPump[0]
    assert htpump.AnnualCoolingEfficiency.Units == "SEER"
    assert htpump.AnnualCoolingEfficiency.Value == 13.0
    assert htpump.AnnualHeatingEfficiency.Units == "HSPF"
    assert htpump.AnnualHeatingEfficiency.Value == 7.7
    assert htpump.BackupAnnualHeatingEfficiency.Units == "AFUE"
    assert htpump.BackupAnnualHeatingEfficiency.Value == 0.98

    measure1 = root.Project.ProjectDetails.Measures.Measure[0]
    assert (
        measure1.InstalledComponents.InstalledComponent[0].attrib["id"]
        == "installed-component-1"
    )
    assert (
        measure1.InstalledComponents.InstalledComponent[1].attrib["id"]
        == "installed-component-2"
    )
    assert not hasattr(measure1, "InstalledComponent")
    assert measure1.InstalledComponents.getnext() == measure1.extension

    measure2 = root.Project.ProjectDetails.Measures.Measure[1]
    assert (
        measure2.InstalledComponents.InstalledComponent[0].attrib["id"]
        == "installed-component-3"
    )
    assert (
        measure2.InstalledComponents.InstalledComponent[1].attrib["id"]
        == "installed-component-4"
    )
    assert not hasattr(measure2, "InstalledComponent")


def test_clothes_dryer():
    root = convert_hpxml_and_parse(hpxml_dir / "clothes_dryer.xml")

    dryer1 = root.Building.BuildingDetails.Appliances.ClothesDryer[0]
    assert dryer1.Type == "dryer"
    assert dryer1.Location == "laundry room"
    assert dryer1.FuelType == "natural gas"
    assert dryer1.EnergyFactor == 2.5
    assert dryer1.ControlType == "timer"
    assert not hasattr(dryer1, "EfficiencyFactor")

    dryer2 = root.Building.BuildingDetails.Appliances.ClothesDryer[1]
    assert dryer2.Type == "all-in-one combination washer/dryer"
    assert dryer2.Location == "basement"
    assert dryer2.FuelType == "electricity"
    assert dryer2.EnergyFactor == 5.0
    assert dryer2.ControlType == "temperature"
    assert not hasattr(dryer2, "EfficiencyFactor")


def test_enclosure_attics_and_roofs():
    with pytest.warns(None) as record:
        root = convert_hpxml_and_parse(hpxml_dir / "enclosure_attics_and_roofs.xml")
    assert len(record) == 5
    assert record[0].message.args[0] == "Cannot find a roof attached to attic-3."
    assert record[1].message.args[0] == "Cannot find a roof attached to attic-3."
    assert record[2].message.args[0] == "Cannot find a roof attached to attic-5."
    assert record[3].message.args[0] == "Cannot find a knee wall attached to attic-9."
    assert record[4].message.args[0] == "Cannot find a roof attached to attic-11."

    enclosure1 = root.Building[0].BuildingDetails.Enclosure
    assert not hasattr(enclosure1, "AtticAndRoof")
    assert not hasattr(enclosure1, "ExteriorAdjacentTo")

    attic1 = enclosure1.Attics.Attic[0]
    assert not attic1.AtticType.Attic.Vented  # unvented attic
    assert attic1.AttachedToRoof.attrib["idref"] == "roof-1"
    assert attic1.AttachedToWall.attrib["idref"] == "wall-1"
    attic2 = enclosure1.Attics.Attic[1]
    assert attic2.AtticType.Attic.extension.Vented == "unknown"  # venting unknown attic
    assert attic2.AttachedToFrameFloor.attrib["idref"] == "attic-floor-1"
    attic3 = enclosure1.Attics.Attic[2]
    assert attic3.AtticType.Attic.Vented  # vented attic
    attic4 = enclosure1.Attics.Attic[3]
    assert hasattr(attic4.AtticType, "FlatRoof")
    attic5 = enclosure1.Attics.Attic[4]
    assert hasattr(attic5.AtticType, "CathedralCeiling")
    attic6 = enclosure1.Attics.Attic[5]
    assert attic6.AtticType.Attic.CapeCod
    attic7 = enclosure1.Attics.Attic[6]
    assert hasattr(attic7.AtticType, "Other")

    roof1 = enclosure1.Roofs.Roof[0]
    assert roof1.Area == 1118.5
    assert roof1.RoofType == "shingles"
    assert roof1.RoofColor == "dark"
    assert roof1.SolarAbsorptance == 0.7
    assert roof1.Emittance == 0.9
    assert roof1.Pitch == 6.0
    assert roof1.Rafters.Size == "2x4"
    assert roof1.Rafters.Material == "wood"
    assert not hasattr(roof1, "RoofArea")
    assert not hasattr(roof1, "Insulation")

    roof2 = enclosure1.Roofs.Roof[1]
    assert roof2.Area == 559.25
    assert roof2.RoofType == "shingles"
    assert roof2.RoofColor == "medium"
    assert roof2.SolarAbsorptance == 0.6
    assert roof2.Emittance == 0.7
    assert roof2.Pitch == 6.0
    assert roof2.Insulation.SystemIdentifier.attrib["id"] == "attic-roof-insulation-1"
    assert roof2.Insulation.InsulationGrade == 3
    assert roof2.Insulation.InsulationCondition == "good"
    assert roof2.Insulation.Layer.InstallationType == "cavity"
    assert roof2.Insulation.Layer.NominalRValue == 7.5
    assert not hasattr(roof2, "Rafters")

    assert enclosure1.Walls.Wall[0].AtticWallType == "knee wall"
    assert not hasattr(enclosure1.Walls.Wall[1], "AtticWallType")

    assert (
        enclosure1.FrameFloors.FrameFloor[0].SystemIdentifier.attrib["id"]
        == "attic-floor-0"
    )
    assert enclosure1.FrameFloors.FrameFloor[0].InteriorAdjacentTo == "garage"
    assert enclosure1.FrameFloors.FrameFloor[0].Area == 1000.0
    assert not hasattr(enclosure1.FrameFloors.FrameFloor[0], "Insulation")
    assert (
        enclosure1.FrameFloors.FrameFloor[1].SystemIdentifier.attrib["id"]
        == "attic-floor-1"
    )
    assert enclosure1.FrameFloors.FrameFloor[1].InteriorAdjacentTo == "living space"
    assert enclosure1.FrameFloors.FrameFloor[1].Area == 500.0
    assert (
        enclosure1.FrameFloors.FrameFloor[1].Insulation.SystemIdentifier.attrib["id"]
        == "attic-floor-insulation-1"
    )
    assert enclosure1.FrameFloors.FrameFloor[1].Insulation.InsulationGrade == 1
    assert enclosure1.FrameFloors.FrameFloor[1].Insulation.InsulationCondition == "poor"
    assert (
        enclosure1.FrameFloors.FrameFloor[1].Insulation.AssemblyEffectiveRValue == 5.5
    )

    enclosure2 = root.Building[1].BuildingDetails.Enclosure
    assert not hasattr(enclosure2, "AtticAndRoof")
    assert not hasattr(enclosure2, "ExteriorAdjacentTo")

    attic8 = enclosure2.Attics.Attic[0]
    assert attic8.AtticType.Attic.CapeCod  # cape cod
    assert attic8.AttachedToRoof.attrib["idref"] == "roof-3"
    assert attic8.AttachedToWall.attrib["idref"] == "wall-3"
    attic9 = enclosure2.Attics.Attic[1]
    assert attic9.AtticType.Attic.extension.Vented == "unknown"  # venting unknown attic
    assert attic9.AttachedToFrameFloor.attrib["idref"] == "attic-floor-8"

    roof3 = enclosure2.Roofs.Roof[0]
    assert roof3.Rafters.Size == "2x6"
    assert roof3.Rafters.Material == "wood"
    assert not hasattr(roof3, "RoofArea")
    assert not hasattr(roof3, "Insulation")

    roof4 = enclosure2.Roofs.Roof[1]
    assert roof4.Insulation.SystemIdentifier.attrib["id"] == "attic-roof-insulation-2"
    assert roof4.Insulation.InsulationGrade == 2
    assert roof4.Insulation.InsulationCondition == "fair"
    assert roof4.Insulation.Layer.InstallationType == "cavity"
    assert roof4.Insulation.Layer.NominalRValue == 7.5
    assert not hasattr(roof4, "Rafters")

    roof5 = enclosure2.Roofs.Roof[2]
    assert roof5.InteriorAdjacentTo == "living space"
    assert roof5.Area == 140.0

    assert enclosure2.Walls.Wall[0].AtticWallType == "knee wall"
    assert not hasattr(enclosure2.Walls.Wall[1], "AtticWallType")

    assert (
        enclosure2.FrameFloors.FrameFloor[0].SystemIdentifier.attrib["id"]
        == "attic-floor-8"
    )
    assert enclosure2.FrameFloors.FrameFloor[0].InteriorAdjacentTo == "living space"
    assert enclosure2.FrameFloors.FrameFloor[0].Area == 700.0
    assert (
        enclosure2.FrameFloors.FrameFloor[0].Insulation.SystemIdentifier.attrib["id"]
        == "attic-floor-insulation-2"
    )
    assert enclosure2.FrameFloors.FrameFloor[0].Insulation.InsulationGrade == 1
    assert enclosure2.FrameFloors.FrameFloor[0].Insulation.InsulationCondition == "poor"
    assert (
        enclosure2.FrameFloors.FrameFloor[0].Insulation.AssemblyEffectiveRValue == 5.5
    )

    buildingconstruction1 = root.Building[
        0
    ].BuildingDetails.BuildingSummary.BuildingConstruction
    buildingconstruction2 = root.Building[
        1
    ].BuildingDetails.BuildingSummary.BuildingConstruction
    buildingconstruction3 = root.Building[
        2
    ].BuildingDetails.BuildingSummary.BuildingConstruction
    buildingconstruction4 = root.Building[
        3
    ].BuildingDetails.BuildingSummary.BuildingConstruction
    buildingconstruction5 = root.Building[
        4
    ].BuildingDetails.BuildingSummary.BuildingConstruction
    buildingconstruction6 = root.Building[
        5
    ].BuildingDetails.BuildingSummary.BuildingConstruction
    buildingconstruction7 = root.Building[
        6
    ].BuildingDetails.BuildingSummary.BuildingConstruction
    assert (
        buildingconstruction1.AtticType.Attic.extension.Vented == "unknown"
    )  # venting unknown attic
    assert hasattr(buildingconstruction2.AtticType, "CathedralCeiling")
    assert buildingconstruction3.AtticType.Attic.Vented  # vented attic
    assert not buildingconstruction4.AtticType.Attic.Vented  # unvented attic
    assert hasattr(buildingconstruction5.AtticType, "FlatRoof")
    assert buildingconstruction6.AtticType.Attic.CapeCod  # cape cod
    assert hasattr(buildingconstruction7.AtticType, "Other")

    with pytest.raises(Exception) as execinfo:
        convert_hpxml_and_parse(hpxml_dir / "enclosure_missing_attic_type.xml")
    assert execinfo.value.args[0] == (
        "enclosure_missing_attic_type.xml was not able to be translated "
        "because 'AtticType' of attic-1 is unknown."
    )


def test_enclosure_foundation():
    root = convert_hpxml_and_parse(hpxml_dir / "enclosure_foundation.xml")

    ff1 = root.Building.BuildingDetails.Enclosure.FrameFloors.FrameFloor[0]
    assert (
        ff1.getparent()
        .getparent()
        .Foundations.Foundation.AttachedToFrameFloor[0]
        .attrib["idref"]
        == "framefloor-1"
    )
    assert ff1.FloorCovering == "hardwood"
    assert ff1.Area == 1350.0
    assert ff1.Insulation.AssemblyEffectiveRValue == 39.3
    assert not hasattr(ff1.Insulation, "InsulationLocation")
    assert not hasattr(ff1.Insulation, "Layer")

    ff2 = root.Building.BuildingDetails.Enclosure.FrameFloors.FrameFloor[1]
    assert (
        ff2.getparent()
        .getparent()
        .Foundations.Foundation.AttachedToFrameFloor[1]
        .attrib["idref"]
        == "framefloor-2"
    )
    assert ff2.FloorCovering == "carpet"
    assert ff2.Area == 1350.0
    assert ff2.Insulation.InsulationGrade == 1
    assert ff2.Insulation.InsulationCondition == "poor"
    assert ff2.Insulation.Layer[0].InstallationType == "continuous - exterior"
    assert ff2.Insulation.Layer[0].NominalRValue == 30.0
    assert ff2.Insulation.Layer[0].Thickness == 1.5
    assert ff2.Insulation.Layer[1].InstallationType == "continuous - exterior"
    assert ff2.Insulation.Layer[1].NominalRValue == 8.0
    assert ff2.Insulation.Layer[1].Thickness == 0.25
    assert not hasattr(ff2.Insulation, "InsulationLocation")

    fw1 = root.Building[0].BuildingDetails.Enclosure.FoundationWalls.FoundationWall[0]
    assert (
        fw1.getparent()
        .getparent()
        .Foundations.Foundation.AttachedToFoundationWall[0]
        .attrib["idref"]
        == "foundationwall-1"
    )
    assert not hasattr(fw1, "ExteriorAdjacentTo")
    assert fw1.InteriorAdjacentTo == "basement - unconditioned"
    assert fw1.Type == "concrete block"
    assert fw1.Length == 120
    assert fw1.Height == 8
    assert fw1.Area == 960
    assert fw1.Thickness == 4
    assert fw1.DepthBelowGrade == 6
    assert not hasattr(fw1, "AdjacentTo")
    assert fw1.Insulation.InsulationGrade == 3
    assert fw1.Insulation.InsulationCondition == "good"
    assert fw1.Insulation.AssemblyEffectiveRValue == 5.0
    assert not hasattr(fw1.Insulation, "Location")

    fw2 = root.Building[0].BuildingDetails.Enclosure.FoundationWalls.FoundationWall[1]
    assert (
        fw2.getparent()
        .getparent()
        .Foundations.Foundation.AttachedToFoundationWall[1]
        .attrib["idref"]
        == "foundationwall-2"
    )
    assert not hasattr(fw2, "ExteriorAdjacentTo")
    assert fw2.InteriorAdjacentTo == "living space"
    assert fw2.Type == "concrete block"
    assert fw2.Length == 60
    assert fw2.Height == 8
    assert fw2.Area == 480
    assert fw2.Thickness == 7
    assert fw2.DepthBelowGrade == 8
    assert not hasattr(fw2, "AdjacentTo")
    assert fw2.Insulation.InsulationGrade == 1
    assert fw2.Insulation.InsulationCondition == "poor"
    assert not hasattr(fw2.Insulation, "Location")
    assert fw2.Insulation.Layer[0].InstallationType == "continuous - exterior"
    assert fw2.Insulation.Layer[0].InsulationMaterial.Batt == "fiberglass"
    assert fw2.Insulation.Layer[0].NominalRValue == 8.9
    assert fw2.Insulation.Layer[0].Thickness == 1.5
    assert fw2.Insulation.Layer[1].InstallationType == "cavity"
    assert fw2.Insulation.Layer[1].InsulationMaterial.Rigid == "eps"
    assert fw2.Insulation.Layer[1].NominalRValue == 15.0
    assert fw2.Insulation.Layer[1].Thickness == 3.0

    fw3 = root.Building[1].BuildingDetails.Enclosure.FoundationWalls.FoundationWall[0]
    assert (
        fw3.getparent()
        .getparent()
        .Foundations.Foundation[0]
        .AttachedToFoundationWall[0]
        .attrib["idref"]
        == "foundationwall-3"
    )
    assert (
        fw3.ExteriorAdjacentTo == "ground"
    )  # make sure that 'ambient' maps to 'ground'
    assert not hasattr(fw3, "InteriorAdjacentTo")
    assert fw3.Type == "solid concrete"
    assert fw3.Length == 40
    assert fw3.Height == 10
    assert fw3.Area == 400
    assert fw3.Thickness == 3
    assert fw3.DepthBelowGrade == 10
    assert not hasattr(fw3, "AdjacentTo")
    assert fw3.Insulation.InsulationGrade == 2
    assert fw3.Insulation.InsulationCondition == "fair"
    assert not hasattr(fw3.Insulation, "Location")

    fw4 = root.Building[1].BuildingDetails.Enclosure.FoundationWalls.FoundationWall[1]
    assert fw4.ExteriorAdjacentTo == "crawlspace"
    assert not hasattr(fw4, "InteriorAdjacentTo")
    assert not hasattr(fw4, "AdjacentTo")

    fw5 = root.Building[1].BuildingDetails.Enclosure.FoundationWalls.FoundationWall[2]
    assert fw5.ExteriorAdjacentTo == "basement - unconditioned"
    assert not hasattr(fw5, "InteriorAdjacentTo")
    assert not hasattr(fw5, "AdjacentTo")

    fw6 = root.Building[1].BuildingDetails.Enclosure.FoundationWalls.FoundationWall[3]
    assert fw6.InteriorAdjacentTo == "crawlspace"
    assert not hasattr(fw6, "ExteriorAdjacentTo")
    assert not hasattr(fw6, "AdjacentTo")

    fw7 = root.Building[1].BuildingDetails.Enclosure.FoundationWalls.FoundationWall[4]
    assert fw7.ExteriorAdjacentTo == "basement - unconditioned"
    assert not hasattr(fw7, "InteriorAdjacentTo")
    assert not hasattr(fw7, "AdjacentTo")

    slab1 = root.Building.BuildingDetails.Enclosure.Slabs.Slab[0]
    assert (
        slab1.getparent()
        .getparent()
        .Foundations.Foundation.AttachedToSlab.attrib["idref"]
        == "slab-1"
    )
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
    root = convert_hpxml_and_parse(hpxml_dir / "enclosure_walls.xml")

    wall1 = root.Building.BuildingDetails.Enclosure.Walls.Wall[0]
    assert wall1.ExteriorAdjacentTo == "outside"
    assert wall1.InteriorAdjacentTo == "living space"
    assert hasattr(wall1.WallType, "WoodStud")
    assert wall1.Thickness == 0.5
    assert wall1.Area == 750
    assert wall1.Azimuth == 0
    assert wall1.Siding == "wood siding"
    assert wall1.SolarAbsorptance == 0.6
    assert wall1.Emittance == 0.7
    assert wall1.Insulation.InsulationGrade == 1
    assert wall1.Insulation.InsulationCondition == "good"
    assert not hasattr(wall1.Insulation, "InsulationLocation")
    assert wall1.Insulation.Layer[0].InstallationType == "continuous - exterior"
    assert wall1.Insulation.Layer[0].InsulationMaterial.Rigid == "xps"
    assert wall1.Insulation.Layer[0].NominalRValue == 5.5
    assert wall1.Insulation.Layer[0].Thickness == 1.5
    assert wall1.Insulation.Layer[1].InstallationType == "cavity"
    assert wall1.Insulation.Layer[1].InsulationMaterial.Batt == "fiberglass"
    assert wall1.Insulation.Layer[1].NominalRValue == 12.0
    assert wall1.Insulation.Layer[1].Thickness == 3.5


def test_windows():
    root = convert_hpxml_and_parse(hpxml_dir / "enclosure_windows_skylights.xml")

    win1 = root.Building[0].BuildingDetails.Enclosure.Windows.Window[0]
    assert win1.Area == 108.0
    assert win1.Azimuth == 0
    assert win1.UFactor == 0.33
    assert win1.SHGC == 0.45
    assert win1.NFRCCertified
    assert win1.VisibleTransmittance == 0.9
    assert win1.ExteriorShading[0].Type == "solar screens"
    assert win1.ExteriorShading[1].Type == "evergreen tree"
    assert win1.InteriorShading.SystemIdentifier.attrib["id"] == "interior-shading-0"
    assert win1.InteriorShading.Type == "light shades"
    assert win1.InteriorShading.SummerShadingCoefficient == 0.7
    assert win1.InteriorShading.WinterShadingCoefficient == 0.7
    assert win1.MoveableInsulation.RValue == 5.5
    assert win1.AttachedToWall.attrib["idref"] == "wall-1"
    assert not hasattr(win1, "Treatments")
    assert not hasattr(win1, "InteriorShadingFactor")
    assert not hasattr(win1, "MovableInsulationRValue")

    win2 = root.Building[0].BuildingDetails.Enclosure.Windows.Window[1]
    assert win2.GlassLayers == "single-pane"
    assert win2.StormWindow.GlassType == "low-e"
    assert win2.ExteriorShading[0].Type == "solar film"

    win3 = root.Building[0].BuildingDetails.Enclosure.Windows.Window[2]
    assert hasattr(win3, "WindowFilm")

    skylight1 = root.Building[0].BuildingDetails.Enclosure.Skylights.Skylight[0]
    assert skylight1.Area == 20.0
    assert skylight1.UFactor == 0.25
    assert skylight1.SHGC == 0.60
    assert skylight1.ExteriorShading[0].Type == "solar screens"
    assert skylight1.ExteriorShading[1].Type == "building"
    assert (
        skylight1.InteriorShading.SystemIdentifier.attrib["id"] == "interior-shading-3"
    )
    assert skylight1.InteriorShading.Type == "dark shades"
    assert skylight1.InteriorShading.SummerShadingCoefficient == 0.65
    assert skylight1.InteriorShading.WinterShadingCoefficient == 0.65
    assert skylight1.MoveableInsulation.RValue == 3.5
    assert skylight1.AttachedToRoof.attrib["idref"] == "roof-1"
    assert skylight1.Pitch == 6.0
    assert not hasattr(skylight1, "Treatments")
    assert not hasattr(skylight1, "InteriorShadingFactor")
    assert not hasattr(skylight1, "MovableInsulationRValue")

    win4 = root.Building[1].BuildingDetails.Enclosure.Windows.Window[0]
    assert win4.Area == 108.0
    assert win4.Azimuth == 0
    assert win4.UFactor == 0.33
    assert win4.SHGC == 0.45
    assert win4.NFRCCertified
    assert win4.VisibleTransmittance == 0.9
    assert win4.ExteriorShading[0].Type == "evergreen tree"
    assert win4.InteriorShading.SystemIdentifier.attrib["id"] == "interior-shading-4"
    assert win4.InteriorShading.SummerShadingCoefficient == 0.7
    assert win4.InteriorShading.WinterShadingCoefficient == 0.7
    assert win4.MoveableInsulation.RValue == 5.5
    assert win4.AttachedToWall.attrib["idref"] == "wall-2"
    assert not hasattr(win4, "Treatments")
    assert not hasattr(win4, "InteriorShadingFactor")
    assert not hasattr(win4, "MovableInsulationRValue")

    skylight2 = root.Building[1].BuildingDetails.Enclosure.Skylights.Skylight[0]
    assert skylight2.ExteriorShading[0].Type == "solar film"
    assert (
        skylight2.InteriorShading.SystemIdentifier.attrib["id"] == "interior-shading-5"
    )
    assert skylight2.InteriorShading.Type == "light shades"
    assert skylight2.InteriorShading.SummerShadingCoefficient == 0.55
    assert skylight2.InteriorShading.WinterShadingCoefficient == 0.55
    assert skylight2.AttachedToRoof.attrib["idref"] == "roof-2"
    assert not hasattr(skylight2, "InteriorShadingFactor")


def test_standard_locations():
    root = convert_hpxml_and_parse(hpxml_dir / "standard_locations.xml")

    wall1 = root.Building[0].BuildingDetails.Enclosure.Walls.Wall[0]
    assert wall1.ExteriorAdjacentTo == "outside"
    assert wall1.InteriorAdjacentTo == "living space"
    wall2 = root.Building[0].BuildingDetails.Enclosure.Walls.Wall[1]
    assert wall2.ExteriorAdjacentTo == "ground"
    assert wall2.InteriorAdjacentTo == "basement - unconditioned"
    wall3 = root.Building[0].BuildingDetails.Enclosure.Walls.Wall[2]
    assert wall3.ExteriorAdjacentTo == "other housing unit"
    assert wall3.InteriorAdjacentTo == "crawlspace"
    wall4 = root.Building[0].BuildingDetails.Enclosure.Walls.Wall[3]
    assert wall4.ExteriorAdjacentTo == "garage"
    assert wall4.InteriorAdjacentTo == "other"

    hvac_dist1 = root.Building[0].BuildingDetails.Systems.HVAC.HVACDistribution[0]
    assert (
        hvac_dist1.DistributionSystemType.AirDistribution.AirDistributionType
        == "regular velocity"
    )
    duct1 = hvac_dist1.DistributionSystemType.AirDistribution.Ducts[0]
    assert duct1.DuctType == "supply"
    assert duct1.DuctLocation == "attic - unconditioned"
    duct2 = hvac_dist1.DistributionSystemType.AirDistribution.Ducts[1]
    assert duct2.DuctType == "supply"
    assert duct2.DuctLocation == "basement - unconditioned"
    duct3 = hvac_dist1.DistributionSystemType.AirDistribution.Ducts[2]
    assert duct3.DuctType == "supply"
    assert duct3.DuctLocation == "living space"
    duct4 = hvac_dist1.DistributionSystemType.AirDistribution.Ducts[3]
    assert duct4.DuctType == "return"
    assert duct4.DuctLocation == "crawlspace - unvented"
    duct5 = hvac_dist1.DistributionSystemType.AirDistribution.Ducts[4]
    assert duct5.DuctType == "return"
    assert duct5.DuctLocation == "crawlspace - vented"
    duct6 = hvac_dist1.DistributionSystemType.AirDistribution.Ducts[5]
    assert duct6.DuctType == "return"
    assert duct6.DuctLocation == "unconditioned space"

    wall5 = root.Building[1].BuildingDetails.Enclosure.Walls.Wall[0]
    assert wall5.ExteriorAdjacentTo == "outside"
    assert wall5.InteriorAdjacentTo == "living space"
    wall6 = root.Building[1].BuildingDetails.Enclosure.Walls.Wall[1]
    assert wall6.ExteriorAdjacentTo == "ground"
    assert wall6.InteriorAdjacentTo == "basement - unconditioned"
    wall7 = root.Building[1].BuildingDetails.Enclosure.Walls.Wall[2]
    assert wall7.ExteriorAdjacentTo == "other housing unit"
    assert wall7.InteriorAdjacentTo == "crawlspace"
    wall8 = root.Building[1].BuildingDetails.Enclosure.Walls.Wall[3]
    assert wall8.ExteriorAdjacentTo == "garage"
    assert wall8.InteriorAdjacentTo == "other"

    hvac_dist2 = root.Building[1].BuildingDetails.Systems.HVAC.HVACDistribution[0]
    assert (
        hvac_dist2.DistributionSystemType.AirDistribution.AirDistributionType
        == "regular velocity"
    )
    duct7 = hvac_dist2.DistributionSystemType.AirDistribution.Ducts[0]
    assert duct7.DuctType == "supply"
    assert duct7.DuctLocation == "attic - unconditioned"
    duct8 = hvac_dist2.DistributionSystemType.AirDistribution.Ducts[1]
    assert duct8.DuctType == "supply"
    assert duct8.DuctLocation == "basement - unconditioned"
    duct9 = hvac_dist2.DistributionSystemType.AirDistribution.Ducts[2]
    assert duct9.DuctType == "supply"
    assert duct9.DuctLocation == "living space"
    duct10 = hvac_dist2.DistributionSystemType.AirDistribution.Ducts[3]
    assert duct10.DuctType == "return"
    assert duct10.DuctLocation == "crawlspace - unvented"
    duct11 = hvac_dist2.DistributionSystemType.AirDistribution.Ducts[4]
    assert duct11.DuctType == "return"
    assert duct11.DuctLocation == "crawlspace - vented"
    duct12 = hvac_dist2.DistributionSystemType.AirDistribution.Ducts[5]
    assert duct12.DuctType == "return"
    assert duct12.DuctLocation == "unconditioned space"

    # Make sure we're not unintentionally changing elements that shouldn't be
    assert (
        root.XMLTransactionHeaderInformation.XMLGeneratedBy == "unconditioned basement"
    )


def test_lighting():
    root = convert_hpxml_and_parse(hpxml_dir / "lighting.xml")

    ltg1 = root.Building[0].BuildingDetails.Lighting
    assert not hasattr(ltg1, "LightingFractions")
    ltg_grp1 = ltg1.LightingGroup[0]
    assert ltg_grp1.SystemIdentifier.attrib["id"] == "lighting-fraction-1"
    assert ltg_grp1.FractionofUnitsInLocation == 0.5
    assert hasattr(ltg_grp1.LightingType, "Incandescent")
    ltg_grp2 = ltg1.LightingGroup[1]
    assert ltg_grp2.SystemIdentifier.attrib["id"] == "lighting-fraction-2"
    assert ltg_grp2.FractionofUnitsInLocation == 0.1
    assert hasattr(ltg_grp2.LightingType, "CompactFluorescent")
    ltg_grp3 = ltg1.LightingGroup[2]
    assert ltg_grp3.SystemIdentifier.attrib["id"] == "lighting-fraction-3"
    assert ltg_grp3.FractionofUnitsInLocation == 0.4
    assert hasattr(ltg_grp3.LightingType, "FluorescentTube")

    ltg2 = root.Building[1].BuildingDetails.Lighting
    assert not hasattr(ltg2, "LightingFractions")
    ltg_grp5 = ltg2.LightingGroup[0]
    assert ltg_grp5.SystemIdentifier.attrib["id"] == "lighting-fraction-4"
    assert ltg_grp5.FractionofUnitsInLocation == 0.1
    assert hasattr(ltg_grp5.LightingType, "Incandescent")
    ltg_grp6 = ltg2.LightingGroup[1]
    assert ltg_grp6.SystemIdentifier.attrib["id"] == "lighting-fraction-5"
    assert ltg_grp6.FractionofUnitsInLocation == 0.2
    assert hasattr(ltg_grp6.LightingType, "CompactFluorescent")
    ltg_grp7 = ltg2.LightingGroup[2]
    assert ltg_grp7.SystemIdentifier.attrib["id"] == "lighting-fraction-6"
    assert ltg_grp7.FractionofUnitsInLocation == 0.2
    assert hasattr(ltg_grp7.LightingType, "FluorescentTube")
    ltg_grp8 = ltg2.LightingGroup[3]
    assert ltg_grp8.SystemIdentifier.attrib["id"] == "lighting-fraction-7"
    assert ltg_grp8.FractionofUnitsInLocation == 0.5
    assert hasattr(ltg_grp8.LightingType, "LightEmittingDiode")


def test_deprecated_items():
    root = convert_hpxml_and_parse(hpxml_dir / "deprecated_items.xml")

    whsystem1 = root.Building[
        0
    ].BuildingDetails.Systems.WaterHeating.WaterHeatingSystem[0]
    assert whsystem1.WaterHeaterInsulation.Jacket.JacketRValue == 5
    assert not hasattr(whsystem1.WaterHeaterInsulation, "Pipe")
    hw_dist1 = root.Building[
        0
    ].BuildingDetails.Systems.WaterHeating.HotWaterDistribution[0]
    assert hw_dist1.PipeInsulation.PipeRValue == 3.0
    whsystem2 = root.Building[
        0
    ].BuildingDetails.Systems.WaterHeating.WaterHeatingSystem[1]
    assert whsystem2.WaterHeaterInsulation.Jacket.JacketRValue == 5.5
    assert not hasattr(whsystem2.WaterHeaterInsulation, "Pipe")
    hw_dist2 = root.Building[
        0
    ].BuildingDetails.Systems.WaterHeating.HotWaterDistribution[1]
    assert hw_dist2.PipeInsulation.PipeRValue == 3.5
    whsystem3 = root.Building[
        1
    ].BuildingDetails.Systems.WaterHeating.WaterHeatingSystem[0]
    assert not hasattr(whsystem3, "WaterHeaterInsulation")
    hw_dist3 = root.Building[
        1
    ].BuildingDetails.Systems.WaterHeating.HotWaterDistribution[0]
    assert hw_dist3.PipeInsulation.PipeRValue == 5.0

    pp1 = root.Building[0].BuildingDetails.Pools.Pool.PoolPumps.PoolPump[0]
    assert pp1.PumpSpeed.HoursPerDay == 3
    assert not hasattr(pp1, "HoursPerDay")
    pp2 = root.Building[0].BuildingDetails.Pools.Pool.PoolPumps.PoolPump[1]
    assert pp2.PumpSpeed.HoursPerDay == 4
    assert not hasattr(pp2, "HoursPerDay")
    pp3 = root.Building[1].BuildingDetails.Pools.Pool.PoolPumps.PoolPump[0]
    assert pp3.PumpSpeed.Power == 250
    assert pp3.PumpSpeed.HoursPerDay == 5
    assert not hasattr(pp3, "HoursPerDay")

    consumption1 = root.Building[
        0
    ].BuildingDetails.BuildingSummary.AnnualEnergyUse.ConsumptionInfo[0]
    assert consumption1.ConsumptionType.Water.WaterType == "indoor water"
    assert consumption1.ConsumptionType.Water.UnitofMeasure == "kcf"
    assert consumption1.ConsumptionDetail.Consumption == 100
    consumption2 = root.Building[
        0
    ].BuildingDetails.BuildingSummary.AnnualEnergyUse.ConsumptionInfo[1]
    assert consumption2.ConsumptionType.Water.WaterType == "outdoor water"
    assert consumption2.ConsumptionType.Water.UnitofMeasure == "ccf"
    assert consumption2.ConsumptionDetail.Consumption == 200
    consumption3 = root.Building[
        0
    ].BuildingDetails.BuildingSummary.AnnualEnergyUse.ConsumptionInfo[2]
    assert consumption3.ConsumptionType.Water.WaterType == "indoor water"
    assert consumption3.ConsumptionType.Water.UnitofMeasure == "gal"
    assert consumption3.ConsumptionDetail.Consumption == 300
    consumption4 = root.Building[
        1
    ].BuildingDetails.BuildingSummary.AnnualEnergyUse.ConsumptionInfo[0]
    assert consumption4.ConsumptionType.Water.WaterType == "indoor water"
    assert consumption4.ConsumptionType.Water.UnitofMeasure == "cf"
    assert consumption4.ConsumptionDetail.Consumption == 400

    wh1 = root.Building[0].BuildingDetails.Systems.WaterHeating
    assert (
        wh1.AnnualEnergyUse.ConsumptionInfo.ConsumptionType.Water.WaterType
        == "indoor and outdoor water"
    )
    assert (
        wh1.AnnualEnergyUse.ConsumptionInfo.ConsumptionType.Water.UnitofMeasure
        == "Mgal"
    )
    assert wh1.AnnualEnergyUse.ConsumptionInfo.ConsumptionDetail.Consumption == 500
    wh2 = root.Building[1].BuildingDetails.Systems.WaterHeating
    assert (
        wh2.AnnualEnergyUse.ConsumptionInfo.ConsumptionType.Water.WaterType
        == "indoor water"
    )
    assert (
        wh2.AnnualEnergyUse.ConsumptionInfo.ConsumptionType.Water.UnitofMeasure == "gal"
    )
    assert wh2.AnnualEnergyUse.ConsumptionInfo.ConsumptionDetail.Consumption == 600


def test_desuperheater_flexibility():
    root = convert_hpxml_and_parse(hpxml_dir / "desuperheater_flexibility.xml")

    whsystem1 = root.Building[
        0
    ].BuildingDetails.Systems.WaterHeating.WaterHeatingSystem[0]
    assert not hasattr(whsystem1, "HasGeothermalDesuperheater")
    assert whsystem1.UsesDesuperheater
    assert not hasattr(whsystem1, "RelatedHeatingSystem")
    assert whsystem1.RelatedHVACSystem.attrib["idref"] == "heating-system-1"
    whsystem2 = root.Building[
        0
    ].BuildingDetails.Systems.WaterHeating.WaterHeatingSystem[1]
    assert not hasattr(whsystem2, "HasGeothermalDesuperheater")
    assert not whsystem2.UsesDesuperheater
    assert not hasattr(whsystem2, "RelatedHeatingSystem")
    assert whsystem2.RelatedHVACSystem.attrib["idref"] == "heatpump-1"
    whsystem3 = root.Building[
        1
    ].BuildingDetails.Systems.WaterHeating.WaterHeatingSystem[0]
    assert not hasattr(whsystem3, "HasGeothermalDesuperheater")
    assert whsystem3.UsesDesuperheater
    assert not hasattr(whsystem3, "RelatedHeatingSystem")
    assert whsystem3.RelatedHVACSystem.attrib["idref"] == "heating-system-2"


def test_inverter_efficiency():
    root = convert_hpxml_and_parse(hpxml_dir / "inverter_efficiency.xml")

    for pv_system in root.Building[0].BuildingDetails.Systems.Photovoltaics.PVSystem:
        assert pv_system.InverterEfficiency == 0.9
