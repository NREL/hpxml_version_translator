from collections import defaultdict
from copy import deepcopy
import datetime as dt
from deprecated import deprecated
from lxml import etree, objectify
import os
import pathlib
import re
import tempfile
from typing import Tuple, Union, BinaryIO, List
import io
import warnings

from hpxml_version_translator import exceptions as exc

File = Union[str, bytes, os.PathLike, BinaryIO]


def pathobj_to_str(x: File) -> Union[str, BinaryIO]:
    """Convert pathlib.Path object (if it is one) to a path string

    lxml doesn't like pathlib.Path objects, so change them to a string if
    necessary first.

    :param x: filepath
    :type x: pathlib.Path or str or file-like object
    :return: file path string
    :rtype: str or whatever was passed in
    """
    if isinstance(x, pathlib.PurePath):
        return str(x)
    elif (
        isinstance(x, str)
        or isinstance(x, io.BufferedWriter)
        or isinstance(x, io.BytesIO)
    ):
        return x
    else:  # tempfile.NamedTemporaryFile
        return x.name


def convert_str_version_to_tuple(version: str) -> Tuple[int]:
    schema_version = list(map(int, version.split(".")))
    schema_version.extend((3 - len(schema_version)) * [0])
    return schema_version


def detect_hpxml_version(hpxmlfilename: File) -> List[int]:
    doc = etree.parse(pathobj_to_str(hpxmlfilename))
    return convert_str_version_to_tuple(doc.getroot().attrib["schemaVersion"])


def get_hpxml_versions(major_version: Union[int, None] = None) -> List[str]:
    schemas_dir = pathlib.Path(__file__).resolve().parent / "schemas"
    schema_versions = []
    for schema_dir in schemas_dir.iterdir():
        if not schema_dir.is_dir() or schema_dir.name == "v1.1.1":
            continue
        tree = etree.parse(str(schema_dir / "HPXMLDataTypes.xsd"))
        root = tree.getroot()
        ns = {"xs": root.nsmap["xs"]}
        schema_versions.extend(
            root.xpath(
                '//xs:simpleType[@name="schemaVersionType"]/xs:restriction/xs:enumeration/@value',
                namespaces=ns,
                smart_strings=False,
            )
        )
        if major_version:
            schema_versions = list(
                filter(
                    lambda x: convert_str_version_to_tuple(x)[0] == major_version,
                    schema_versions,
                )
            )
    return schema_versions


def add_after(
    parent_el: etree._Element, list_of_el_names: List[str], el_to_add: etree._Element
) -> None:
    for sibling_name in reversed(list_of_el_names):
        try:
            sibling = getattr(parent_el, sibling_name)[-1]
        except AttributeError:
            continue
        else:
            sibling.addnext(el_to_add)
            return
    parent_el.insert(0, el_to_add)


def add_before(
    parent_el: etree._Element, list_of_el_names: List[str], el_to_add: etree._Element
) -> None:
    for sibling_name in list_of_el_names:
        try:
            sibling = getattr(parent_el, sibling_name)[0]
        except AttributeError:
            continue
        else:
            sibling.addprevious(el_to_add)
            return
    parent_el.append(el_to_add)


def convert_hpxml_to_version(
    hpxml_version: str, hpxml_file: File, hpxml_out_file: File
) -> None:

    # Validate that the hpxml_version requested is a valid one.
    hpxml_version_strs = get_hpxml_versions()
    schema_version_requested = convert_str_version_to_tuple(hpxml_version)
    major_version_requested = schema_version_requested[0]
    if hpxml_version not in hpxml_version_strs:
        raise exc.HpxmlTranslationError(
            f"HPXML version {hpxml_version} is not valid. Must be one of {', '.join(hpxml_version_strs)}."
        )

    # Validate that the hpxml_version requested is a newer one that the current one.
    schema_version_file = detect_hpxml_version(hpxml_file)
    major_version_file = schema_version_file[0]
    if major_version_requested <= major_version_file:
        raise exc.HpxmlTranslationError(
            f"HPXML version requested is {hpxml_version} but input file major version is {schema_version_file[0]}"
        )

    version_translator_funcs = {
        1: convert_hpxml1_to_2,
        2: convert_hpxml2_to_3,
        3: convert_hpxml3_to_4,
    }
    current_file = hpxml_file
    with tempfile.TemporaryDirectory() as tmpdir:
        for current_version in range(major_version_file, major_version_requested):
            next_version = current_version + 1
            if current_version + 1 == major_version_requested:
                next_file = hpxml_out_file
                version_translator_funcs[current_version](
                    current_file, next_file, hpxml_version
                )
            else:
                next_file = pathlib.Path(tmpdir, f"{next_version}.xml")
                version_translator_funcs[current_version](current_file, next_file)
            current_file = next_file


@deprecated(version="1.0.0", reason="Use convert_hpxml_to_version instead")
def convert_hpxml_to_3(hpxml_file: File, hpxml3_file: File) -> None:
    convert_hpxml_to_version("3.0", hpxml_file, hpxml3_file)


def convert_hpxml1_to_2(
    hpxml1_file: File, hpxml2_file: File, version: str = "2.3"
) -> None:
    """Convert an HPXML v1 file to HPXML v2

    :param hpxml1_file: HPXML v1 input file
    :type hpxml1_file: pathlib.Path, str, or file-like
    :param hpxml2_file: HPXML v2 output file
    :type hpxml2_file: pathlib.Path, str, or file-like
    :param version: Target version
    :type version: str
    """

    if version not in get_hpxml_versions(major_version=2):
        raise exc.HpxmlTranslationError(
            "convert_hpxml1_to_2 must have valid target version of 2.x, got {version}."
        )

    # Load Schemas
    schemas_dir = pathlib.Path(__file__).resolve().parent / "schemas"
    hpxml1_schema_doc = etree.parse(str(schemas_dir / "v1.1.1" / "HPXML.xsd"))
    hpxml1_ns = hpxml1_schema_doc.getroot().attrib["targetNamespace"]
    hpxml1_schema = etree.XMLSchema(hpxml1_schema_doc)
    hpxml2_schema_doc = etree.parse(str(schemas_dir / "v2.3" / "HPXML.xsd"))
    hpxml2_ns = hpxml2_schema_doc.getroot().attrib["targetNamespace"]
    hpxml2_schema = etree.XMLSchema(hpxml2_schema_doc)

    E = objectify.ElementMaker(
        namespace=hpxml2_ns, nsmap={None: hpxml2_ns}, annotate=False
    )
    xpkw = {"namespaces": {"h": hpxml2_ns}}

    # Ensure we're working with valid HPXML v1.x (earlier versions should validate against v1.1.1 schema)
    hpxml1_doc = objectify.parse(pathobj_to_str(hpxml1_file))
    hpxml1_schema.assertValid(hpxml1_doc)

    # Change the namespace of every element to use the HPXML v2 namespace
    # https://stackoverflow.com/a/51660868/11600307
    change_ns_xslt = etree.parse(
        str(pathlib.Path(__file__).resolve().parent / "change_namespace.xsl")
    )
    hpxml2_doc = hpxml1_doc.xslt(
        change_ns_xslt, orig_namespace=f"'{hpxml1_ns}'", new_namespace=f"'{hpxml2_ns}'"
    )
    root = hpxml2_doc.getroot()

    # Change version
    root.attrib["schemaVersion"] = version

    # TODO: Moved the BPI 2400 elements and renamed/reorganized them.

    # Renamed element AttachedToCAZ under water heater to fix a typo.
    for el in root.xpath("//h:WaterHeatingSystem/h:AtachedToCAZ", **xpkw):
        el.tag = f"{{{hpxml2_ns}}}AttachedToCAZ"

    # Removed "batch heater" from SolarCollectorLoopType in lieu of the previously
    # added "integrated collector storage" enumeration on SolarThermalCollectorType.
    for batch_heater in root.xpath(
        '//h:SolarThermal/h:SolarThermalSystem[h:CollectorLoopType="batch heater"]',
        **xpkw,
    ):
        if not hasattr(batch_heater, "CollectorType"):
            add_after(
                batch_heater,
                ["CollectorLoopType"],
                E.CollectorType("integrated collector storage"),
            )
        batch_heater.remove(batch_heater.CollectorLoopType)

    # Throw a warning if there are BPI2400 elements and move it into an extension
    bpi2400_els = root.xpath("//h:BPI2400Inputs", **xpkw)
    if bpi2400_els:
        warnings.warn(
            "BPI2400Inputs in v1.1.1 are ambiguous and aren't translated into their "
            "corresponding elements in v2.x. They have been moved to an extension instead."
        )
    for el in bpi2400_els:
        parent_el = el.getparent()
        if not hasattr(parent_el, "extension"):
            parent_el.append(E.extension())
        parent_el.extension.append(deepcopy(el))
        parent_el.remove(el)

    # Write out new file
    hpxml2_doc.write(pathobj_to_str(hpxml2_file), pretty_print=True, encoding="utf-8")
    hpxml2_schema.assertValid(hpxml2_doc)


def convert_hpxml2_to_3(
    hpxml2_file: File, hpxml3_file: File, version: str = "3.0"
) -> None:
    """Convert an HPXML v2 file to HPXML v3

    :param hpxml2_file: HPXML v2 input file
    :type hpxml2_file: pathlib.Path, str, or file-like
    :param hpxml3_file: HPXML v3 output file
    :type hpxml3_file: pathlib.Path, str, or file-like
    :param version: Target version
    :type version: str
    """

    if version not in get_hpxml_versions(major_version=3):
        raise exc.HpxmlTranslationError(
            "convert_hpxml2_to_3 must have valid target version of 3.x, got {version}."
        )

    # Load Schemas
    schemas_dir = pathlib.Path(__file__).resolve().parent / "schemas"
    hpxml2_schema_doc = etree.parse(str(schemas_dir / "v2.3" / "HPXML.xsd"))
    hpxml2_ns = hpxml2_schema_doc.getroot().attrib["targetNamespace"]
    hpxml2_schema = etree.XMLSchema(hpxml2_schema_doc)
    hpxml3_schema_doc = etree.parse(str(schemas_dir / "v3.0" / "HPXML.xsd"))
    hpxml3_ns = hpxml3_schema_doc.getroot().attrib["targetNamespace"]
    hpxml3_schema = etree.XMLSchema(hpxml3_schema_doc)

    E = objectify.ElementMaker(
        namespace=hpxml3_ns, nsmap={None: hpxml3_ns}, annotate=False
    )
    xpkw = {"namespaces": {"h": hpxml3_ns}}

    # Ensure we're working with valid HPXML v2.x (earlier versions should validate against v2.3 schema)
    hpxml2_doc = objectify.parse(pathobj_to_str(hpxml2_file))
    hpxml2_schema.assertValid(hpxml2_doc)

    # Change the namespace of every element to use the HPXML v3 namespace
    # https://stackoverflow.com/a/51660868/11600307
    change_ns_xslt = etree.parse(
        str(pathlib.Path(__file__).resolve().parent / "change_namespace.xsl")
    )
    hpxml3_doc = hpxml2_doc.xslt(
        change_ns_xslt, orig_namespace=f"'{hpxml2_ns}'", new_namespace=f"'{hpxml3_ns}'"
    )
    root = hpxml3_doc.getroot()

    # Change version
    root.attrib["schemaVersion"] = version

    # Standardized location mapping
    location_map = {
        "ambient": "outside",  # 'ambient' will be mapped to 'ground' for FoundationWall
        "conditioned space": "living space",
        "unconditioned basement": "basement - unconditioned",
        "unconditioned attic": "attic - unconditioned",
        "unvented crawlspace": "crawlspace - unvented",
        "vented crawlspace": "crawlspace - vented",
    }
    foundation_location_map = deepcopy(location_map)
    foundation_location_map["ambient"] = "ground"

    # Fixing project ids
    # https://github.com/hpxmlwg/hpxml/pull/197
    # This is really messy. I can see why we fixed it.

    def get_pre_post_from_building_id(building_id):
        event_type = root.xpath(
            "h:Building[h:BuildingID/@id=$bldgid]/h:ProjectStatus/h:EventType/text()",
            smart_strings=False,
            bldgid=building_id,
            **xpkw,
        )
        if len(event_type) == 1:
            if event_type[0] in (
                "proposed workscope",
                "approved workscope",
                "construction-period testing/daily test out",
                "job completion testing/final inspection",
                "quality assurance/monitoring",
            ):
                return "post"
            elif event_type[0] in ("audit", "preconstruction"):
                return "pre"
            else:
                return None
        else:
            return None

    for i, project in enumerate(root.xpath("h:Project", **xpkw), 1):

        # Add the ProjectID element if it isn't there
        if not hasattr(project, "ProjectID"):
            add_after(project, ["BuildingID"], E.ProjectID(id=f"project-{i}"))
        building_ids_by_pre_post = defaultdict(set)

        # Gather together the buildings in BuildingID and ProjectSystemIdentifiers
        building_id = project.BuildingID.attrib["id"]
        building_ids_by_pre_post[get_pre_post_from_building_id(building_id)].add(
            building_id
        )
        for psi in project.xpath("h:ProjectDetails/h:ProjectSystemIdentifiers", **xpkw):
            building_id = psi.attrib.get("id")
            building_ids_by_pre_post[get_pre_post_from_building_id(building_id)].add(
                building_id
            )

        for pre_post in ("pre", "post"):
            if len(building_ids_by_pre_post[pre_post]) == 0:
                for building_id in root.xpath("h:Building/h:BuildingID/@id", **xpkw):
                    if get_pre_post_from_building_id(building_id) == pre_post:
                        building_ids_by_pre_post[pre_post].add(building_id)

        # If there are more than one of each pre and post, throw an error
        if len(building_ids_by_pre_post["pre"]) == 0:
            raise exc.HpxmlTranslationError(
                f"Project[{i}] has no references to Building nodes with an 'audit' or 'preconstruction' EventType."
            )
        elif len(building_ids_by_pre_post["pre"]) > 1:
            raise exc.HpxmlTranslationError(
                f"Project[{i}] has more than one reference to Building nodes with an "
                "'audit' or 'preconstruction' EventType."
            )
        if len(building_ids_by_pre_post["post"]) == 0:
            raise exc.HpxmlTranslationError(
                f"Project[{i}] has no references to Building nodes with a post retrofit EventType."
            )
        elif len(building_ids_by_pre_post["post"]) > 1:
            raise exc.HpxmlTranslationError(
                f"Project[{i}] has more than one reference to Building nodes with a post retrofit EventType."
            )
        pre_building_id = building_ids_by_pre_post["pre"].pop()
        post_building_id = building_ids_by_pre_post["post"].pop()

        # Add the pre building
        project.ProjectID.addnext(E.PreBuildingID(id=pre_building_id))
        for el in root.xpath(
            "h:Building/h:BuildingID[@id=$bldgid]/*", bldgid=pre_building_id, **xpkw
        ):
            project.PreBuildingID.append(deepcopy(el))

        # Add the post building
        project.PreBuildingID.addnext(E.PostBuildingID(id=post_building_id))
        for el in root.xpath(
            "h:Building/h:BuildingID[@id=$bldgid]/*", bldgid=post_building_id, **xpkw
        ):
            project.PostBuildingID.append(deepcopy(el))

        # Move the ambiguous BuildingID to an extension
        if not hasattr(project, "extension"):
            project.append(E.extension())
        project.extension.append(deepcopy(project.BuildingID))
        project.remove(project.BuildingID)

        # Move the ProjectSystemIdentifiers to an extension
        for psi in project.xpath("h:ProjectDetails/h:ProjectSystemIdentifiers", **xpkw):
            project.extension.append(deepcopy(psi))
            project.ProjectDetails.remove(psi)

    # Green Building Verification
    # https://github.com/hpxmlwg/hpxml/pull/66
    # This next one is covered here because the BPI-2101 verification didn't exist in v2, so no need to translate it
    # https://github.com/hpxmlwg/hpxml/pull/210

    energy_score_els = root.xpath(
        "h:Building/h:BuildingDetails/h:BuildingSummary/h:BuildingConstruction/h:EnergyScore",
        **xpkw,
    )
    for i, es in enumerate(energy_score_els, 1):
        bldg_details = es.getparent().getparent().getparent()
        if not hasattr(bldg_details, "GreenBuildingVerifications"):
            add_after(
                bldg_details,
                ["BuildingSummary", "ClimateandRiskZones"],
                E.GreenBuildingVerifications(),
            )
        gbv = E.GreenBuildingVerification(
            E.SystemIdentifier(id=f"energy-score-{i}"),
            E.Type(
                {
                    "US DOE Home Energy Score": "Home Energy Score",
                    "RESNET HERS": "HERS Index Score",
                    "other": "other",
                }[str(es.ScoreType)]
            ),
            E.Body(
                {
                    "US DOE Home Energy Score": "US DOE",
                    "RESNET HERS": "RESNET",
                    "other": "other",
                }[str(es.ScoreType)]
            ),
            E.Metric(str(es.Score)),
        )
        if hasattr(es, "OtherScoreType"):
            gbv.Type.addnext(E.OtherType(str(es.OtherScoreType)))
        if hasattr(es, "ScoreDate"):
            gbv.append(E.Year(dt.datetime.strptime(str(es.ScoreDate), "%Y-%m-%d").year))
        if hasattr(es, "extension"):
            gbv.append(deepcopy(es.extension))
        bldg_details.GreenBuildingVerifications.append(gbv)
        es.getparent().remove(es)

    for i, prog_cert in enumerate(
        root.xpath("h:Project/h:ProjectDetails/h:ProgramCertificate", **xpkw), 1
    ):
        project_details = prog_cert.getparent()
        bldg_id = project_details.getparent().PostBuildingID.attrib["id"]
        bldg_details = root.xpath(
            "h:Building[h:BuildingID/@id=$bldgid]/h:BuildingDetails",
            bldgid=bldg_id,
            **xpkw,
        )[0]
        if not hasattr(bldg_details, "GreenBuildingVerifications"):
            add_after(
                bldg_details,
                ["BuildingSummary", "ClimateandRiskZones"],
                E.GreenBuildingVerifications(),
            )
        gbv = E.GreenBuildingVerification(
            E.SystemIdentifier(id=f"program-certificate-{i}"),
            E.Type(
                {
                    "Home Performance with Energy Star": "Home Performance with ENERGY STAR",
                    "LEED Certified": "LEED For Homes",
                    "LEED Silver": "LEED For Homes",
                    "LEED Gold": "LEED For Homes",
                    "LEED Platinum": "LEED For Homes",
                    "other": "other",
                }[str(prog_cert)]
            ),
        )
        if hasattr(project_details, "CertifyingOrganization"):
            gbv.append(E.Body(str(project_details.CertifyingOrganization)))
        m = re.match(r"LEED (\w+)$", str(prog_cert))
        if m:
            gbv.append(E.Rating(m.group(1)))
        if hasattr(project_details, "CertifyingOrganizationURL"):
            gbv.append(E.URL(str(project_details.CertifyingOrganizationURL)))
        if hasattr(project_details, "YearCertified"):
            gbv.append(E.Year(int(project_details.YearCertified)))
        bldg_details.GreenBuildingVerifications.append(gbv)

    for i, es_home_ver in enumerate(
        root.xpath("h:Project/h:ProjectDetails/h:EnergyStarHomeVersion", **xpkw)
    ):
        bldg_id = es_home_ver.getparent().getparent().PostBuildingID.attrib["id"]
        bldg_details = root.xpath(
            "h:Building[h:BuildingID/@id=$bldgid]/h:BuildingDetails",
            bldgid=bldg_id,
            **xpkw,
        )[0]
        if not hasattr(bldg_details, "GreenBuildingVerifications"):
            add_after(
                bldg_details,
                ["BuildingSummary", "ClimateandRiskZones"],
                E.GreenBuildingVerifications(),
            )
        gbv = E.GreenBuildingVerification(
            E.SystemIdentifier(id=f"energy-star-home-{i}"),
            E.Type("ENERGY STAR Certified Homes"),
            E.Version(str(es_home_ver)),
        )
        bldg_details.GreenBuildingVerifications.append(gbv)

    for el_name in (
        "CertifyingOrganization",
        "CertifyingOrganizationURL",
        "YearCertified",
        "ProgramCertificate",
        "EnergyStarHomeVersion",
    ):
        for el in root.xpath(f"//h:ProjectDetails/h:{el_name}", **xpkw):
            el.getparent().remove(el)

    # Addressing Inconsistencies
    # https://github.com/hpxmlwg/hpxml/pull/124

    for el in root.xpath("//h:HeatPump/h:AnnualCoolEfficiency", **xpkw):
        el.tag = f"{{{hpxml3_ns}}}AnnualCoolingEfficiency"
    for el in root.xpath("//h:HeatPump/h:AnnualHeatEfficiency", **xpkw):
        el.tag = f"{{{hpxml3_ns}}}AnnualHeatingEfficiency"

    # Replaces Measure/InstalledComponent with Measure/InstalledComponents/InstalledComponent
    for i, ic in enumerate(
        root.xpath(
            "h:Project/h:ProjectDetails/h:Measures/h:Measure/h:InstalledComponent",
            **xpkw,
        )
    ):
        ms = ic.getparent()
        if not hasattr(ms, "InstalledComponents"):
            add_before(ms, ["extension"], E.InstalledComponents())
        ms.InstalledComponents.append(deepcopy(ic))
        ms.remove(ic)

    # Replaces WeatherStation/SystemIdentifiersInfo with WeatherStation/SystemIdentifier
    for el in root.xpath("//h:WeatherStation/h:SystemIdentifiersInfo", **xpkw):
        el.tag = f"{{{hpxml3_ns}}}SystemIdentifier"

    # Renames "central air conditioning" to "central air conditioner" for CoolingSystemType
    for el in root.xpath("//h:CoolingSystem/h:CoolingSystemType", **xpkw):
        if el == "central air conditioning":
            el._setText("central air conditioner")

    # Renames HeatPump/BackupAFUE to BackupAnnualHeatingEfficiency, accepts 0-1 instead of 1-100
    for bkupafue in root.xpath(
        "h:Building/h:BuildingDetails/h:Systems/h:HVAC/h:HVACPlant/h:HeatPump/h:BackupAFUE",
        **xpkw,
    ):
        heatpump = bkupafue.getparent()
        add_before(
            heatpump,
            [
                "BackupHeatingCapacity",
                "BackupHeatingSwitchoverTemperature",
                "FractionHeatLoadServed",
                "FractionCoolLoadServed",
                "FloorAreaServed",
                "AnnualCoolingEfficiency",
                "AnnualHeatingEfficiency",
                "extension",
            ],
            E.BackupAnnualHeatingEfficiency(
                E.Units("AFUE"), E.Value(f"{float(bkupafue.text) / 100}")
            ),
        )
        heatpump.remove(bkupafue)

    # Renames FoundationWall/BelowGradeDepth to FoundationWall/DepthBelowGrade
    for el in root.xpath("//h:FoundationWall/h:BelowGradeDepth", **xpkw):
        el.tag = f"{{{hpxml3_ns}}}DepthBelowGrade"

    # Clothes Dryer CEF
    # https://github.com/hpxmlwg/hpxml/pull/145

    for el in root.xpath("//h:ClothesDryer/h:EfficiencyFactor", **xpkw):
        el.tag = f"{{{hpxml3_ns}}}EnergyFactor"

    # Enclosure
    # https://github.com/hpxmlwg/hpxml/pull/181

    for fw in root.xpath(
        "h:Building/h:BuildingDetails/h:Enclosure/h:Foundations/h:Foundation/h:FoundationWall",
        **xpkw,
    ):
        enclosure = fw.getparent().getparent().getparent()
        foundation = fw.getparent()

        add_before(
            foundation,
            ["AttachedToFrameFloor", "AttachedToSlab", "AnnualEnergyUse", "extension"],
            E.AttachedToFoundationWall(idref=fw.SystemIdentifier.attrib["id"]),
        )
        if not hasattr(enclosure, "FoundationWalls"):
            add_after(
                enclosure,
                [
                    "AirInfiltration",
                    "Attics",
                    "Foundations",
                    "Garages",
                    "Roofs",
                    "RimJoists",
                    "Walls",
                ],
                E.FoundationWalls(),
            )
        enclosure.FoundationWalls.append(deepcopy(fw))
        this_fw = enclosure.FoundationWalls.FoundationWall[-1]

        if hasattr(this_fw, "AdjacentTo"):
            try:
                fw_boundary = foundation_location_map[str(fw.AdjacentTo)]
            except KeyError:
                fw_boundary = str(fw.AdjacentTo)  # retain unchanged location name
            try:
                boundary_v3 = {
                    "other housing unit": "Exterior",
                    "ground": "Exterior",
                    "ambient": "Exterior",
                    "attic": "Exterior",
                    "garage": "Exterior",
                    "living space": "Interior",
                    "unconditioned basement": "Interior",
                    "crawlspace": "Interior",
                }[str(fw.AdjacentTo)]
                if boundary_v3 == "Interior" and hasattr(foundation, "FoundationType"):
                    # Check that this matches the Foundation/FoundationType if available
                    if fw.AdjacentTo == "unconditioned basement" and (
                        foundation.xpath(
                            'count(h:FoundationType/h:Basement/h:Conditioned[text()="true"])',
                            **xpkw,
                        )
                        > 0
                        or not hasattr(foundation.FoundationType, "Basement")
                    ):
                        boundary_v3 = "Exterior"
                    elif fw.AdjacentTo == "crawlspace" and not hasattr(
                        foundation.FoundationType, "Crawlspace"
                    ):
                        boundary_v3 = "Exterior"
                add_after(
                    this_fw,
                    ["SystemIdentifier", "ExternalResource", "AttachedToSpace"],
                    getattr(E, f"{boundary_v3}AdjacentTo")(fw_boundary),
                )
            except KeyError:
                pass
            this_fw.remove(this_fw.AdjacentTo)

        foundation.remove(fw)

    # Attics
    for bldg_const in root.xpath(
        "h:Building/h:BuildingDetails/h:BuildingSummary/h:BuildingConstruction", **xpkw
    ):
        if hasattr(bldg_const, "AtticType"):
            if bldg_const.AtticType == "vented attic":
                bldg_const.AtticType = E.AtticType(E.Attic(E.Vented(True)))
            elif bldg_const.AtticType == "unvented attic":
                bldg_const.AtticType = E.AtticType(E.Attic(E.Vented(False)))
            elif bldg_const.AtticType == "flat roof":
                bldg_const.AtticType = E.AtticType(E.FlatRoof())
            elif bldg_const.AtticType == "cathedral ceiling":
                bldg_const.AtticType = E.AtticType(E.CathedralCeiling())
            elif bldg_const.AtticType == "cape cod":
                bldg_const.AtticType = E.AtticType(E.Attic(E.CapeCod(True)))
            elif bldg_const.AtticType == "other":
                bldg_const.AtticType = E.AtticType(E.Other())
            elif bldg_const.AtticType == "venting unknown attic":
                bldg_const.AtticType = E.AtticType(
                    E.Attic(E.extension(E.Vented("unknown")))
                )

    for i, attic in enumerate(
        root.xpath(
            "h:Building/h:BuildingDetails/h:Enclosure/h:AtticAndRoof/h:Attics/h:Attic",
            **xpkw,
        )
    ):
        enclosure = attic.getparent().getparent().getparent()
        this_attic = deepcopy(attic)
        this_attic_type = None
        if hasattr(this_attic, "AtticType"):
            this_attic_type = this_attic.AtticType
            if this_attic.AtticType == "vented attic":
                this_attic.AtticType = E.AtticType(E.Attic(E.Vented(True)))
            elif this_attic.AtticType == "unvented attic":
                this_attic.AtticType = E.AtticType(E.Attic(E.Vented(False)))
            elif this_attic.AtticType == "flat roof":
                this_attic.AtticType = E.AtticType(E.FlatRoof())
            elif this_attic.AtticType == "cathedral ceiling":
                this_attic.AtticType = E.AtticType(E.CathedralCeiling())
            elif this_attic.AtticType == "cape cod":
                this_attic.AtticType = E.AtticType(E.Attic(E.CapeCod(True)))
            elif this_attic.AtticType == "other":
                this_attic.AtticType = E.AtticType(E.Other())
            elif this_attic.AtticType == "venting unknown attic":
                this_attic.AtticType = E.AtticType(
                    E.Attic(E.extension(E.Vented("unknown")))
                )
        else:
            raise exc.HpxmlTranslationError(
                f"{hpxml2_file.name} was not able to be translated "
                f"because 'AtticType' of {this_attic.SystemIdentifier.attrib['id']} is unknown."
            )

        if not hasattr(enclosure, "Attics"):
            add_after(enclosure, ["AirInfiltration"], E.Attics())

        # rearrange AttachedToRoof
        if hasattr(this_attic, "AttachedToRoof"):
            attached_to_roof = deepcopy(this_attic.AttachedToRoof)
            this_attic.remove(
                this_attic.AttachedToRoof
            )  # remove the AttachedToRoof of HPXML v2
            add_after(
                this_attic,
                ["SystemIdentifier", "AttachedToSpace", "AtticType", "VentilationRate"],
                attached_to_roof,
            )

        # find the wall with the same id and add AtticWallType = knee wall
        if hasattr(this_attic, "AtticKneeWall"):
            knee_wall_id = this_attic.AtticKneeWall.attrib["idref"]
            try:
                knee_wall = root.xpath(
                    "h:Building/h:BuildingDetails/h:Enclosure/h:Walls/h:Wall[h:SystemIdentifier/@id=$sysid]",
                    sysid=knee_wall_id,
                    **xpkw,
                )[0]
            except IndexError:
                warnings.warn(
                    f"Cannot find a knee wall attached to {this_attic.SystemIdentifier.attrib['id']}."
                )
            else:
                if not hasattr(knee_wall, "AtticWallType"):
                    add_after(
                        knee_wall,
                        [
                            "SystemIdentifier",
                            "ExteriorAdjacentTo",
                            "InteriorAdjacentTo",
                        ],
                        E.AtticWallType("knee wall"),
                    )
                add_before(
                    this_attic,
                    ["AttachedToFrameFloor", "AnnualEnergyUse", "extension"],
                    E.AttachedToWall(idref=knee_wall_id),
                )

        # create a FrameFloor adjacent to the attic and assign the area below to Area
        # and then copy AtticFloorInsulation over to Insulation of the frame floor
        if hasattr(this_attic, "AtticFloorInsulation") or (
            this_attic_type not in ["cathedral ceiling", "flat roof", "cape cod"]
        ):
            if not hasattr(enclosure, "FrameFloors"):
                add_before(
                    enclosure,
                    ["Slabs", "Windows", "Skylights", "Doors", "extension"],
                    E.FrameFloors(),
                )
            attic_floor_el = E.FrameFloor(E.SystemIdentifier(id=f"attic-floor-{i}"))
            attic_floor_id = attic_floor_el.SystemIdentifier.attrib["id"]
            add_before(
                this_attic,
                ["AnnualEnergyUse", "extension"],
                E.AttachedToFrameFloor(idref=attic_floor_id),
            )
            if hasattr(this_attic, "Area"):
                attic_floor_el.append(E.Area(float(this_attic.Area)))
            if hasattr(this_attic, "AtticFloorInsulation"):
                attic_floor_insulation = deepcopy(this_attic.AtticFloorInsulation)
                attic_floor_insulation.tag = f"{{{hpxml3_ns}}}Insulation"
                attic_floor_el.append(attic_floor_insulation)
            enclosure.FrameFloors.append(attic_floor_el)

        # find Roof attached to Attic and move Insulation to Roof
        # add insulation to v2 Roofs and these roofs will be converted into hpxml v3 later
        if hasattr(this_attic, "AtticRoofInsulation"):
            roof_insulation = deepcopy(this_attic.AtticRoofInsulation)
            roof_insulation.tag = f"{{{hpxml3_ns}}}Insulation"
            roof_idref = this_attic.AttachedToRoof.attrib["idref"]
            try:
                roof_attached_to_this_attic = root.xpath(
                    "h:Building/h:BuildingDetails/h:Enclosure/h:AtticAndRoof/\
                        h:Roofs/h:Roof[h:SystemIdentifier/@id=$sysid]",
                    sysid=roof_idref,
                    **xpkw,
                )[0]
            except IndexError:
                warnings.warn(
                    f"Cannot find a roof attached to {this_attic.SystemIdentifier.attrib['id']}."
                )
            else:
                add_before(roof_attached_to_this_attic, ["extension"], roof_insulation)

        # translate v2 Attic/Area to the v3 Roof/Area for "cathedral ceiling" and "flat roof"
        if hasattr(this_attic, "Area") and this_attic_type in [
            "cathedral ceiling",
            "flat roof",
        ]:
            try:
                roof_idref = this_attic.AttachedToRoof.attrib["idref"]
                roof_attached_to_this_attic = root.xpath(
                    "h:Building/h:BuildingDetails/h:Enclosure/h:AtticAndRoof/\
                        h:Roofs/h:Roof[h:SystemIdentifier/@id=$sysid]",
                    sysid=roof_idref,
                    **xpkw,
                )[0]
            except IndexError:
                warnings.warn(
                    f"Cannot find a roof attached to {this_attic.SystemIdentifier.attrib['id']}."
                )
            else:
                if not hasattr(roof_attached_to_this_attic, "RoofArea"):
                    add_before(
                        roof_attached_to_this_attic,
                        ["RadiantBarrier", "RadiantBarrierLocation", "extension"],
                        E.RoofArea(this_attic.Area.text),
                    )

        # move Rafters to v2 Roofs and these roofs will be converted into hpxml v3 later
        if hasattr(this_attic, "Rafters"):
            rafters = deepcopy(this_attic.Rafters)
            roof_idref = this_attic.AttachedToRoof.attrib["idref"]
            try:
                roof_attached_to_this_attic = root.xpath(
                    "h:Building/h:BuildingDetails/h:Enclosure/h:AtticAndRoof/\
                        h:Roofs/h:Roof[h:SystemIdentifier/@id=$sysid]",
                    sysid=roof_idref,
                    **xpkw,
                )[0]
            except IndexError:
                warnings.warn(
                    f"Cannot find a roof attached to {this_attic.SystemIdentifier.attrib['id']}."
                )
            else:
                add_after(
                    roof_attached_to_this_attic,
                    [
                        "SystemIdentifier",
                        "ExternalResource",
                        "AttachedToSpace",
                        "RoofColor",
                        "SolarAbsorptance",
                        "Emittance",
                    ],
                    rafters,
                )

        if hasattr(this_attic, "InteriorAdjacentTo") and hasattr(
            this_attic, "AtticType"
        ):
            if this_attic_type in ["cathedral ceiling", "flat roof", "cape cod"]:
                try:
                    roof_idref = this_attic.AttachedToRoof.attrib["idref"]
                    roof_attached_to_this_attic = root.xpath(
                        "h:Building/h:BuildingDetails/h:Enclosure/h:AtticAndRoof/h:Roofs/\
                            h:Roof[h:SystemIdentifier/@id=$sysid]",
                        sysid=roof_idref,
                        **xpkw,
                    )[0]
                except (AttributeError, IndexError):
                    warnings.warn(
                        f"Cannot find a roof attached to {this_attic.SystemIdentifier.attrib['id']}."
                    )
                else:
                    add_after(
                        roof_attached_to_this_attic,
                        ["SystemIdentifier", "ExternalResource", "AttachedToSpace"],
                        E.InteriorAdjacentTo(this_attic.InteriorAdjacentTo.text),
                    )
            else:
                try:
                    floor_idref = this_attic.AttachedToFrameFloor.attrib["idref"]
                    floor_attached_to_this_attic = root.xpath(
                        "h:Building/h:BuildingDetails/h:Enclosure/h:FrameFloors/\
                            h:FrameFloor[h:SystemIdentifier/@id=$sysid]",
                        sysid=floor_idref,
                        **xpkw,
                    )[0]
                except (AttributeError, IndexError):
                    warnings.warn(
                        f"Cannot find a frame floor attached to {this_attic.SystemIdentifier.attrib['id']}."
                    )
                else:
                    add_after(
                        floor_attached_to_this_attic,
                        [
                            "SystemIdentifier",
                            "ExternalResource",
                            "AttachedToSpace",
                            "ExteriorAdjacentTo",
                        ],
                        E.InteriorAdjacentTo(this_attic.InteriorAdjacentTo.text),
                    )

        el_not_in_v3 = [
            "ExteriorAdjacentTo",
            "InteriorAdjacentTo",
            "AtticKneeWall",
            "AtticFloorInsulation",
            "AtticRoofInsulation",
            "Area",
            "Rafters",
        ]
        for el in el_not_in_v3:
            if hasattr(this_attic, el):
                this_attic.remove(this_attic[el])

        enclosure.Attics.append(this_attic)

    # Roofs
    for roof in root.xpath(
        "h:Building/h:BuildingDetails/h:Enclosure/h:AtticAndRoof/h:Roofs/h:Roof", **xpkw
    ):
        enclosure = roof.getparent().getparent().getparent()
        if not hasattr(enclosure, "Roofs"):
            add_after(
                enclosure,
                ["AirInfiltration", "Attics", "Foundations", "Garages"],
                E.Roofs(),
            )
        enclosure.Roofs.append(deepcopy(roof))
        this_roof = enclosure.Roofs.Roof[-1]

        if hasattr(roof, "RoofArea"):
            add_after(
                this_roof,
                [
                    "SystemIdentifier",
                    "ExternalResource",
                    "AttachedToSpace",
                    "InteriorAdjacentTo",
                ],
                E.Area(float(roof.RoofArea)),
            )
            this_roof.remove(this_roof.RoofArea)

        if hasattr(roof, "RoofType"):
            roof_type = str(roof.RoofType)
            this_roof.remove(this_roof.RoofType)  # remove the RoofType of HPXML v2
            add_after(
                this_roof,
                [
                    "SystemIdentifier",
                    "ExternalResource",
                    "AttachedToSpace",
                    "InteriorAdjacentTo",
                    "Area",
                    "Orientation",
                    "Azimuth",
                ],
                E.RoofType(roof_type),
            )

    # remove AtticAndRoof after rearranging all attics and roofs
    for enclosure in root.xpath("h:Building/h:BuildingDetails/h:Enclosure", **xpkw):
        try:
            enclosure.remove(enclosure.AtticAndRoof)
        except AttributeError:
            pass

    # Frame Floors
    for ff in root.xpath(
        "h:Building/h:BuildingDetails/h:Enclosure/h:Foundations/h:Foundation/h:FrameFloor",
        **xpkw,
    ):
        enclosure = ff.getparent().getparent().getparent()
        foundation = ff.getparent()

        add_before(
            foundation,
            ["AttachedToSlab", "AnnualEnergyUse", "extension"],
            E.AttachedToFrameFloor(idref=ff.SystemIdentifier.attrib["id"]),
        )
        if not hasattr(enclosure, "FrameFloors"):
            add_before(
                enclosure,
                ["Slabs", "Windows", "Skylights", "Doors", "extension"],
                E.FrameFloors(),
            )
        this_ff = deepcopy(ff)
        enclosure.FrameFloors.append(this_ff)
        foundation.remove(ff)

    # Slabs
    for slab in root.xpath(
        "h:Building/h:BuildingDetails/h:Enclosure/h:Foundations/h:Foundation/h:Slab",
        **xpkw,
    ):
        enclosure = slab.getparent().getparent().getparent()
        foundation = slab.getparent()

        add_before(
            foundation,
            ["AnnualEnergyUse", "extension"],
            E.AttachedToSlab(idref=slab.SystemIdentifier.attrib["id"]),
        )
        if not hasattr(enclosure, "Slabs"):
            add_before(
                enclosure, ["Windows", "Skylights", "Doors", "extension"], E.Slabs()
            )
        enclosure.Slabs.append(deepcopy(slab))
        foundation.remove(slab)

    # Allow insulation location to be layer-specific
    # https://github.com/hpxmlwg/hpxml/pull/188

    for insulation_location in root.xpath(
        "//h:Insulation/h:InsulationLocation", **xpkw
    ):
        # Insulation location to be layer-specific
        insulation = insulation_location.getparent()
        if hasattr(insulation, "Layer"):
            for layer in insulation.Layer:
                if layer.InstallationType == "continuous":
                    layer.InstallationType._setText(
                        f"continuous - {str(insulation.InsulationLocation)}"
                    )
        insulation.remove(insulation.InsulationLocation)

    # Windows and Skylights
    # Window sub-components
    # https://github.com/hpxmlwg/hpxml/pull/202
    for i, win in enumerate(root.xpath("//h:Window|//h:Skylight", **xpkw)):
        if hasattr(win, "VisibleTransmittance"):
            vis_trans = float(win.VisibleTransmittance)
            win.remove(
                win.VisibleTransmittance
            )  # remove VisibleTransmittance of HPXML v2
            add_after(
                win,
                [
                    "SystemIdentifier",
                    "ExternalResource",
                    "Area",
                    "Quantity",
                    "Azimuth",
                    "Orientation",
                    "FrameType",
                    "GlassLayers",
                    "GlassType",
                    "GasFill",
                    "Condition",
                    "UFactor",
                    "SHGC",
                ],
                E.VisibleTransmittance(vis_trans),
            )
        if hasattr(win, "ExteriorShading"):
            ext_shade = str(win.ExteriorShading)
            win.remove(win.ExteriorShading)  # remove ExteriorShading of HPXML v2
            add_after(
                win,
                [
                    "SystemIdentifier",
                    "ExternalResource",
                    "Area",
                    "Quantity",
                    "Azimuth",
                    "Orientation",
                    "FrameType",
                    "GlassLayers",
                    "GlassType",
                    "GasFill",
                    "Condition",
                    "UFactor",
                    "SHGC",
                    "VisibleTransmittance",
                    "NFRCCertified",
                    "ThirdPartyCertification",
                    "WindowFilm",
                ],
                E.ExteriorShading(
                    E.SystemIdentifier(id=f"exterior-shading-{i}"), E.Type(ext_shade)
                ),
            )
        if hasattr(win, "Treatments"):
            if win.Treatments in ["shading", "solar screen"]:
                treatment_shade = E.ExteriorShading(
                    E.SystemIdentifier(id=f"treatment-shading-{i}"),
                )
                if win.Treatments == "solar screen":
                    treatment_shade.append(E.Type("solar screens"))
                add_after(
                    win,
                    [
                        "SystemIdentifier",
                        "ExternalResource",
                        "Area",
                        "Quantity",
                        "Azimuth",
                        "Orientation",
                        "FrameType",
                        "GlassLayers",
                        "GlassType",
                        "GasFill",
                        "Condition",
                        "UFactor",
                        "SHGC",
                        "VisibleTransmittance",
                        "NFRCCertified",
                        "ThirdPartyCertification",
                        "WindowFilm",
                    ],
                    treatment_shade,
                )
            elif win.Treatments == "window film":
                add_after(
                    win,
                    [
                        "SystemIdentifier",
                        "ExternalResource",
                        "Area",
                        "Quantity",
                        "Azimuth",
                        "Orientation",
                        "FrameType",
                        "GlassLayers",
                        "GlassType",
                        "GasFill",
                        "Condition",
                        "UFactor",
                        "SHGC",
                        "VisibleTransmittance",
                        "NFRCCertified",
                        "ThirdPartyCertification",
                    ],
                    E.WindowFilm(E.SystemIdentifier(id=f"window-film-{i}")),
                )
            win.remove(win.Treatments)
        if hasattr(win, "InteriorShading"):
            cache_interior_shading_type = str(win.InteriorShading)
            win.InteriorShading.clear()
            win.InteriorShading.append(E.SystemIdentifier(id=f"interior-shading-{i}"))
            win.InteriorShading.append(E.Type(cache_interior_shading_type))

        # Window/Skylight Interior Shading Fraction
        # https://github.com/hpxmlwg/hpxml/pull/189
        if hasattr(win, "InteriorShadingFactor"):
            # handles a case where `InteriorShadingFactor` is specified without `InteriorShading`
            if not hasattr(win, "InteriorShading"):
                add_before(
                    win,
                    [
                        "StormWindow",
                        "MoveableInsulation",
                        "Overhangs",
                        "WeatherStripping",
                        "Operable",
                        "LeakinessDescription",
                        "WindowtoWallRatio",
                        "AttachedToWall",
                        "AnnualEnergyUse",
                        "extension",
                    ],
                    E.InteriorShading(E.SystemIdentifier(id=f"interior-shading-{i}")),
                )
            win.InteriorShading.extend(
                [
                    E.SummerShadingCoefficient(float(win.InteriorShadingFactor)),
                    E.WinterShadingCoefficient(float(win.InteriorShadingFactor)),
                ]
            )
            win.remove(win.InteriorShadingFactor)
        if hasattr(win, "MovableInsulationRValue"):
            add_after(
                win,
                [
                    "SystemIdentifier",
                    "ExternalResource",
                    "Area",
                    "Quantity",
                    "Azimuth",
                    "Orientation",
                    "FrameType",
                    "GlassLayers",
                    "GlassType",
                    "GasFill",
                    "Condition",
                    "UFactor",
                    "SHGC",
                    "VisibleTransmittance",
                    "NFRCCertified",
                    "ThirdPartyCertification",
                    "WindowFilm",
                    "ExteriorShading",
                    "InteriorShading",
                    "StormWindow",
                ],
                E.MoveableInsulation(
                    E.SystemIdentifier(id=f"moveable-insulation-{i}"),
                    E.RValue(float(win.MovableInsulationRValue)),
                ),
            )
            win.remove(win.MovableInsulationRValue)
        if hasattr(win, "GlassLayers"):
            if win.GlassLayers in [
                "single-paned with low-e storms",
                "single-paned with storms",
            ]:
                storm_window = E.StormWindow(E.SystemIdentifier(id=f"storm-window-{i}"))
                if win.GlassLayers == "single-paned with low-e storms":
                    storm_window.append(E.GlassType("low-e"))
                win.GlassLayers._setText("single-pane")
                add_after(
                    win,
                    [
                        "SystemIdentifier",
                        "ExternalResource",
                        "Area",
                        "Quantity",
                        "Azimuth",
                        "Orientation",
                        "FrameType",
                        "GlassLayers",
                        "GlassType",
                        "GasFill",
                        "Condition",
                        "UFactor",
                        "SHGC",
                        "VisibleTransmittance",
                        "NFRCCertified",
                        "ThirdPartyCertification",
                        "WindowFilm",
                        "ExteriorShading",
                        "InteriorShading",
                    ],
                    storm_window,
                )

    # Standardize Locations
    # https://github.com/hpxmlwg/hpxml/pull/156

    for el in root.xpath(
        "//h:InteriorAdjacentTo|//h:ExteriorAdjacentTo|//h:DuctLocation|//h:HVACPlant/h:*/h:UnitLocation|//h:WaterHeatingSystem/h:Location|//h:Measure/h:Location",  # noqa E501
        **xpkw,
    ):
        try:
            el._setText(location_map[el.text])
        except (KeyError, AttributeError):
            pass

    # Lighting Fraction Improvements
    # https://github.com/hpxmlwg/hpxml/pull/165

    ltgidx = 0
    for ltgfracs in root.xpath(
        "h:Building/h:BuildingDetails/h:Lighting/h:LightingFractions", **xpkw
    ):
        ltg = ltgfracs.getparent()
        for ltgfrac in ltgfracs.getchildren():
            ltgidx += 1
            ltggroup = E.LightingGroup(
                E.SystemIdentifier(id=f"lighting-fraction-{ltgidx}"),
                E.FractionofUnitsInLocation(ltgfrac.text),
                E.LightingType(),
            )
            if ltgfrac.tag == f"{{{hpxml3_ns}}}FractionIncandescent":
                ltggroup.LightingType.append(E.Incandescent())
            elif ltgfrac.tag == f"{{{hpxml3_ns}}}FractionCFL":
                ltggroup.LightingType.append(E.CompactFluorescent())
            elif ltgfrac.tag == f"{{{hpxml3_ns}}}FractionLFL":
                ltggroup.LightingType.append(E.FluorescentTube())
            elif ltgfrac.tag == f"{{{hpxml3_ns}}}FractionLED":
                ltggroup.LightingType.append(E.LightEmittingDiode())
            add_after(ltg, ["LightingGroup"], ltggroup)
        ltg.remove(ltgfracs)

    # Deprecated items
    # https://github.com/hpxmlwg/hpxml/pull/167

    # Removes WaterHeaterInsulation/Pipe; use HotWaterDistribution/PipeInsulation instead
    for i, pipe in enumerate(root.xpath("//h:WaterHeaterInsulation/h:Pipe", **xpkw), 1):
        waterheating = pipe.getparent().getparent().getparent()
        waterheatingsystem = pipe.getparent().getparent()
        waterheatingsystem_idref = str(waterheatingsystem.SystemIdentifier.attrib["id"])
        try:
            hw_dist = waterheating.xpath(
                "h:HotWaterDistribution[h:AttachedToWaterHeatingSystem/@idref=$sysid]",
                sysid=waterheatingsystem_idref,
                **xpkw,
            )[0]
            add_after(
                hw_dist,
                [
                    "SystemIdentifier",
                    "ExternalResource",
                    "AttachedToWaterHeatingSystem",
                    "SystemType",
                ],
                E.PipeInsulation(E.PipeRValue(float(pipe.PipeRValue))),
            )
        except IndexError:  # handles when there is no attached hot water distribution system
            add_after(
                waterheating,
                ["WaterHeatingSystem", "WaterHeatingControl"],
                E.HotWaterDistribution(
                    E.SystemIdentifier(id=f"hotwater-distribution-{i}"),
                    E.AttachedToWaterHeatingSystem(idref=waterheatingsystem_idref),
                    E.PipeInsulation(E.PipeRValue(float(pipe.PipeRValue))),
                ),
            )
        waterheaterinsualtion = pipe.getparent()
        waterheaterinsualtion.remove(pipe)
        if waterheaterinsualtion.countchildren() == 0:
            waterheaterinsualtion.getparent().remove(waterheaterinsualtion)

    # Removes PoolPump/HoursPerDay; use PoolPump/PumpSpeed/HoursPerDay instead
    for poolpump_hour in root.xpath("//h:PoolPump/h:HoursPerDay", **xpkw):
        poolpump = poolpump_hour.getparent()
        if not hasattr(poolpump, "PumpSpeed"):
            add_before(
                poolpump,
                ["extension"],
                E.PumpSpeed(E.HoursPerDay(float(poolpump_hour))),
            )
        else:
            add_before(
                poolpump.PumpSpeed, ["extension"], E.HoursPerDay(float(poolpump_hour))
            )
        poolpump.remove(poolpump_hour)

    # Removes "indoor water " (note extra trailing space) enumeration from WaterType
    for watertype in root.xpath("//h:WaterType", **xpkw):
        if watertype == "indoor water ":
            watertype._setText(str(watertype).rstrip())

    # Adds desuperheater flexibility
    # https://github.com/hpxmlwg/hpxml/pull/184

    for el in root.xpath("//h:WaterHeatingSystem/h:RelatedHeatingSystem", **xpkw):
        el.tag = f"{{{hpxml3_ns}}}RelatedHVACSystem"
    for el in root.xpath("//h:WaterHeatingSystem/h:HasGeothermalDesuperheater", **xpkw):
        el.tag = f"{{{hpxml3_ns}}}UsesDesuperheater"

    # Handle PV inverter efficiency value
    # https://github.com/hpxmlwg/hpxml/pull/207

    for inverter_efficiency in root.xpath("//h:InverterEfficiency", **xpkw):
        if float(inverter_efficiency) > 1:
            inverter_efficiency._setText(str(float(inverter_efficiency) / 100.0))

    # Write out new file
    hpxml3_doc.write(pathobj_to_str(hpxml3_file), pretty_print=True, encoding="utf-8")
    hpxml3_schema.assertValid(hpxml3_doc)


def convert_hpxml3_to_4(
    hpxml3_file: File, hpxml4_file: File, version: str = "4.0"
) -> None:
    """Convert an HPXML v3 file to HPXML v4

    :param hpxml3_file: HPXML v3 input file
    :type hpxml3_file: pathlib.Path, str, or file-like
    :param hpxml4_file: HPXML v4 output file
    :type hpxml4_file: pathlib.Path, str, or file-like
    """
    if version not in get_hpxml_versions(major_version=4):
        raise exc.HpxmlTranslationError(
            "convert_hpxml3_to_4 must have valid target version of 4.x, got {version}."
        )

    # Load Schemas
    schemas_dir = pathlib.Path(__file__).resolve().parent / "schemas"
    hpxml3_schema_doc = etree.parse(str(schemas_dir / "v3.0" / "HPXML.xsd"))
    hpxml3_ns = hpxml3_schema_doc.getroot().attrib["targetNamespace"]
    hpxml3_schema = etree.XMLSchema(hpxml3_schema_doc)
    hpxml4_schema_doc = etree.parse(str(schemas_dir / "v4.0" / "HPXML.xsd"))
    hpxml4_ns = hpxml4_schema_doc.getroot().attrib["targetNamespace"]
    hpxml4_schema = etree.XMLSchema(hpxml4_schema_doc)

    E = objectify.ElementMaker(
        namespace=hpxml3_ns, nsmap={None: hpxml3_ns}, annotate=False
    )
    xpkw = {"namespaces": {"h": hpxml3_ns}}

    # Ensure we're working with valid HPXML v3.x
    hpxml3_doc = objectify.parse(pathobj_to_str(hpxml3_file))
    hpxml3_schema.assertValid(hpxml3_doc)

    # Change the namespace of every element to use the HPXML v4 namespace
    # https://stackoverflow.com/a/51660868/11600307
    change_ns_xslt = etree.parse(
        str(pathlib.Path(__file__).resolve().parent / "change_namespace.xsl")
    )
    hpxml4_doc = hpxml3_doc.xslt(
        change_ns_xslt, orig_namespace=f"'{hpxml3_ns}'", new_namespace=f"'{hpxml4_ns}'"
    )
    root = hpxml4_doc.getroot()

    # Change version
    root.attrib["schemaVersion"] = "4.0"

    # Move some FoundationWall/Slab insulation properties into their Layer elements
    # https://github.com/hpxmlwg/hpxml/pull/215

    for fwall in root.xpath("//h:FoundationWall", **xpkw):
        if hasattr(fwall, "DistanceToTopOfInsulation"):
            for il in fwall.xpath("h:Insulation/h:Layer", **xpkw):
                add_before(
                    il,
                    ["extension"],
                    E.DistanceToTopOfInsulation(fwall.DistanceToTopOfInsulation.text),
                )
            fwall.remove(fwall.DistanceToTopOfInsulation)
        if hasattr(fwall, "DistanceToBottomOfInsulation"):
            for il in fwall.xpath("h:Insulation/h:Layer", **xpkw):
                add_before(
                    il,
                    ["extension"],
                    E.DistanceToBottomOfInsulation(
                        fwall.DistanceToBottomOfInsulation.text
                    ),
                )
            fwall.remove(fwall.DistanceToBottomOfInsulation)

    for slab in root.xpath("//h:Slab", **xpkw):
        if hasattr(slab, "PerimeterInsulationDepth"):
            for il in slab.xpath("h:PerimeterInsulation/h:Layer", **xpkw):
                add_before(
                    il,
                    ["extension"],
                    E.InsulationDepth(slab.PerimeterInsulationDepth.text),
                )
            slab.remove(slab.PerimeterInsulationDepth)
        if hasattr(slab, "UnderSlabInsulationWidth"):
            for il in slab.xpath("h:UnderSlabInsulation/h:Layer", **xpkw):
                add_before(
                    il,
                    ["extension"],
                    E.InsulationWidth(slab.UnderSlabInsulationWidth.text),
                )
            slab.remove(slab.UnderSlabInsulationWidth)
        if hasattr(slab, "UnderSlabInsulationSpansEntireSlab"):
            for il in slab.xpath("h:UnderSlabInsulation/h:Layer", **xpkw):
                add_before(
                    il,
                    ["extension"],
                    E.InsulationSpansEntireSlab(
                        slab.UnderSlabInsulationSpansEntireSlab.text
                    ),
                )
            slab.remove(slab.UnderSlabInsulationSpansEntireSlab)

    # Battery Capacity
    # https://github.com/hpxmlwg/hpxml/pull/296

    for battery in root.xpath("//h:Battery", **xpkw):
        if hasattr(battery, "NominalCapacity"):
            value = battery.NominalCapacity.text
            battery.NominalCapacity._setText(None)
            battery.NominalCapacity.append(E.Units("Ah"))
            battery.NominalCapacity.append(E.Value(value))
        if hasattr(battery, "UsableCapacity"):
            value = battery.UsableCapacity.text
            battery.UsableCapacity._setText(None)
            battery.UsableCapacity.append(E.Units("Ah"))
            battery.UsableCapacity.append(E.Value(value))

    # Write out new file
    hpxml4_doc.write(pathobj_to_str(hpxml4_file), pretty_print=True, encoding="utf-8")
    hpxml4_schema.assertValid(hpxml4_doc)
