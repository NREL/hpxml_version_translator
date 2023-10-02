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


def test_dhw_recirculation():
    root = convert_hpxml_and_parse(hpxml_dir / "hot_water_recirculation.xml")

    hwd = root.Building[0].BuildingDetails.Systems.WaterHeating.HotWaterDistribution
    assert not hasattr(hwd, "BranchPipingLoopLength")
    assert hwd.SystemType.Recirculation.BranchPipingLength == 50


def test_dehumidifier():
    root = convert_hpxml_and_parse(hpxml_dir / "dehumidifier.xml")

    d1 = root.Building[0].BuildingDetails.Appliances.Dehumidifier[0]
    assert not hasattr(d1, "Efficiency")
    assert d1.EnergyFactor == 1.8

    d2 = root.Building[0].BuildingDetails.Appliances.Dehumidifier[1]
    assert not hasattr(d2, "Efficiency")
    assert not hasattr(d2, "EnergyFactor")


def test_standby_loss():
    root = convert_hpxml_and_parse(hpxml_dir / "commercial_water_heater.xml")

    wh1 = root.Building[0].BuildingDetails.Systems.WaterHeating.WaterHeatingSystem[0]
    assert wh1.StandbyLoss.Units == "F/hr"
    assert wh1.StandbyLoss.Value == 1.0

    wh2 = root.Building[0].BuildingDetails.Systems.WaterHeating.WaterHeatingSystem[1]
    assert not hasattr(wh2, "StandbyLoss")


def test_enclosure_floors():
    root = convert_hpxml_and_parse(hpxml_dir / "enclosure_floors.xml")

    atc = root.Building.BuildingDetails.Enclosure.Attics.Attic
    assert not hasattr(atc, "AttachedToFrameFloor")
    assert hasattr(atc, "AttachedToFloor")

    fnd = root.Building.BuildingDetails.Enclosure.Foundations.Foundation
    assert not hasattr(fnd, "AttachedToFrameFloor")
    assert hasattr(fnd, "AttachedToFloor")
    assert fnd.ThermalBoundary == 'floor'

    enc = root.Building.BuildingDetails.Enclosure
    assert not hasattr(enc, "FrameFloors")
    assert hasattr(enc, "Floors")
    assert len(enc.Floors.Floor) == 4


def test_enclosure_sip_walls():
    root = convert_hpxml_and_parse(hpxml_dir / "enclosure_sip_wall.xml")

    w1 = root.Building.BuildingDetails.Enclosure.Walls.Wall[0]
    assert hasattr(w1.WallType, "StructuralInsulatedPanel")

    w2 = root.Building.BuildingDetails.Enclosure.Walls.Wall[1]
    assert hasattr(w2.WallType, "WoodStud")

    w3 = root.Building.BuildingDetails.Enclosure.Walls.Wall[2]
    assert hasattr(w3.WallType, "StructuralInsulatedPanel")


def test_ducts():
    root = convert_hpxml_and_parse(hpxml_dir / "ducts.xml")

    hvacdist1 = root.Building.BuildingDetails.Systems.HVAC.HVACDistribution[0]
    for i in (0, 1):
        ducts = hvacdist1.DistributionSystemType.AirDistribution.Ducts[i]
        assert hasattr(ducts, "SystemIdentifier")
        assert ducts.SystemIdentifier.attrib['id'] == f"hvacd1_ducts{i}"

    hvacdist2 = root.Building.BuildingDetails.Systems.HVAC.HVACDistribution[1]
    for i in (0, 1):
        ducts = hvacdist2.DistributionSystemType.AirDistribution.Ducts[i]
        assert hasattr(ducts, "SystemIdentifier")
        assert ducts.SystemIdentifier.attrib['id'] == f"hvacd2_ducts{i}"


def test_pv_system():
    root = convert_hpxml_and_parse(hpxml_dir / "pv_sys.xml")

    pv = root.Building[0].BuildingDetails.Systems.Photovoltaics

    for i in (0, 2):
        pv_sys = pv.PVSystem[i]
        assert not hasattr(pv_sys, "InverterEfficiency")
        assert not hasattr(pv_sys, "YearInverterManufactured")

    assert len(pv.Inverter) == 2

    inv1 = pv.Inverter[0]
    assert hasattr(inv1, "SystemIdentifier")
    assert inv1.InverterEfficiency == 0.95

    inv2 = pv.Inverter[1]
    assert hasattr(inv2, "SystemIdentifier")
    assert inv2.YearInverterManufactured == 2019


def test_count():
    root = convert_hpxml_and_parse(hpxml_dir / "count.xml")

    bd = root.Building[0].BuildingDetails
    pd = root.Project.ProjectDetails

    # These shouldn't change
    assert hasattr(bd.BuildingSummary.BuildingConstruction, "NumberofUnits")
    assert hasattr(pd.Measures.Measure, "Quantity")

    # These should change
    assert hasattr(bd.Enclosure.Windows.Window, "Count")
    assert hasattr(bd.Enclosure.Skylights.Skylight, "Count")
    assert hasattr(bd.Enclosure.Doors.Door, "Count")
    assert hasattr(bd.Systems.MechanicalVentilation.VentilationFans.VentilationFan, "Count")
    assert hasattr(bd.Systems.WaterHeating.WaterFixture, "Count")
    assert hasattr(bd.Systems.ElectricVehicleChargers.ElectricVehicleCharger, "Count")
    assert hasattr(bd.Appliances.ClothesWasher, "Count")
    assert hasattr(bd.Appliances.ClothesDryer, "Count")
    assert hasattr(bd.Appliances.Dishwasher, "Count")
    assert hasattr(bd.Appliances.Refrigerator, "Count")
    assert hasattr(bd.Appliances.Freezer, "Count")
    assert hasattr(bd.Appliances.Dehumidifier, "Count")
    assert hasattr(bd.Appliances.CookingRange, "Count")
    assert hasattr(bd.Appliances.Oven, "Count")
    assert hasattr(bd.Lighting.LightingGroup, "Count")
    assert hasattr(bd.Lighting.CeilingFan, "Count")


def test_remote_reference():
    root = convert_hpxml_and_parse(hpxml_dir / "remote_reference.xml")

    for bd in root.Building:
        assert bd.CustomerID.attrib["idref"]
        assert bd.ContractorID.attrib["idref"]
        for aim in bd.BuildingDetails.Enclosure.AirInfiltration.AirInfiltrationMeasurement:
            assert aim.BusinessConductingTest.attrib["idref"]
            assert aim.IndividualConductingTest.attrib["idref"]
        for caz in bd.BuildingDetails.HealthAndSafety.CombustionAppliances.CombustionApplianceZone:
            for cat in caz.CombustionApplianceTest:
                assert cat.CAZAppliance.attrib["idref"]
                assert cat.CombustionVentingSystem.attrib["idref"]

    assert root.Project.PreBuildingID.attrib["idref"]
    assert root.Project.PostBuildingID.attrib["idref"]
    for meas in root.Project.ProjectDetails.Measures.Measure:
        assert meas.InstallingContractor.attrib["idref"]
        assert meas.ReplacedComponents.ReplacedComponent.attrib["idref"]
        assert meas.InstalledComponents.InstalledComponent.attrib["idref"]

    for cons in root.Consumption:
        assert cons.BuildingID.attrib["idref"]
        assert cons.CustomerID.attrib["idref"]
        assert cons.ConsumptionDetails.ConsumptionInfo.UtilityID.attrib["idref"]


def test_geothermal_loop():
    root = convert_hpxml_and_parse(hpxml_dir / "geothermal_loop.xml")

    hvac_plant = root.Building.BuildingDetails.Systems.HVAC.HVACPlant
    for i in (0, 1):
        gshp = hvac_plant.HeatPump[i]
        assert gshp.AttachedToGeothermalLoop.attrib['idref'] == f"gshp{i+1}-geothermal-loop"

        geo_loop = hvac_plant.GeothermalLoop[i]
        assert geo_loop.SystemIdentifier.attrib['id'] == f"gshp{i+1}-geothermal-loop"
        if i == 0:
            assert geo_loop.LoopType == 'closed'
        else:
            assert geo_loop.LoopType == 'open'


def test_max_ambient_co():
    root = convert_hpxml_and_parse(hpxml_dir / "max_ambient_co.xml")

    assert root.Building.BuildingDetails.HealthAndSafety.CombustionAppliances.MaxAmbientCOinLivingSpaceDuringAudit == 2


def test_max_ambient_co_error():
    with pytest.raises(
        exc.HpxmlTranslationError,
        match=r"All MaxAmbientCOinLivingSpaceDuringAudit elements must have the same value.",
    ):
        convert_hpxml_and_parse(hpxml_dir / "max_ambient_co_error.xml")


def test_portable_heater():
    root = convert_hpxml_and_parse(hpxml_dir / "portable_heater.xml")

    for i in (0, 2):
        htgsys = root.Building.BuildingDetails.Systems.HVAC.HVACPlant.HeatingSystem[i]
        assert hasattr(htgsys.HeatingSystemType, "SpaceHeater")


def test_cee_enumeration():
    root = convert_hpxml_and_parse(hpxml_dir / "pool_pumps_and_cee_enum.xml")

    assert root.Building.BuildingDetails.Pools.Pool[0].Pumps.Pump[2].ThirdPartyCertification == "CEE Tier 3"
    assert root.Building.BuildingDetails.Pools.Pool[1].Pumps.Pump[0].ThirdPartyCertification == "CEE Tier 3"


def test_mismatch_version():
    f_out = io.BytesIO()
    with pytest.raises(
        exc.HpxmlTranslationError,
        match=r"convert_hpxml3_to_4 must have valid target version of 4\.x",
    ):
        convert_hpxml3_to_4(hpxml_dir / "version_change.xml", f_out, "2.0")
