from collections import defaultdict
from copy import deepcopy
import datetime as dt
from lxml import etree, objectify
import pathlib
import re

from hpxml_version_translator import exceptions as exc


def pathobj_to_str(x):
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
    else:
        return x


def convert_hpxml2_to_3(hpxml2_file, hpxml3_file):
    """Convert an HPXML v2 file to HPXML v3

    :param hpxml2_file: HPXML v2 input file
    :type hpxml2_file: pathlib.Path, str, or file-like
    :param hpxml3_file: HPXML v3 output file
    :type hpxml3_file: pathlib.Path, str, or file-like
    """

    # Load Schemas
    schemas_dir = pathlib.Path(__file__).resolve().parent / 'schemas'
    hpxml2_schema_doc = etree.parse(str(schemas_dir / 'v2.3' / 'HPXML.xsd'))
    hpxml2_ns = hpxml2_schema_doc.getroot().attrib['targetNamespace']
    hpxml2_schema = etree.XMLSchema(hpxml2_schema_doc)
    hpxml3_schema_doc = etree.parse(str(schemas_dir / 'v3.0' / 'HPXML.xsd'))
    hpxml3_ns = hpxml3_schema_doc.getroot().attrib['targetNamespace']
    hpxml3_schema = etree.XMLSchema(hpxml3_schema_doc)

    E = objectify.ElementMaker(namespace=hpxml3_ns, nsmap={None: hpxml3_ns}, annotate=False)
    xpkw = {'namespaces': {'h': hpxml3_ns}}

    def add_after(parent_el, list_of_el_names, el_to_add):
        for sibling_name in reversed(list_of_el_names):
            try:
                sibling = getattr(parent_el, sibling_name)[-1]
            except AttributeError:
                continue
            else:
                sibling.addnext(el_to_add)
                return
        parent_el.insert(0, el_to_add)

    def add_before(parent_el, list_of_el_names, el_to_add):
        for sibling_name in list_of_el_names:
            try:
                sibling = getattr(parent_el, sibling_name)[0]
            except AttributeError:
                continue
            else:
                sibling.addprevious(el_to_add)
                return
        parent_el.append(el_to_add)

    # Ensure we're working with valid HPXML v2.x (earlier versions should validate against v2.3 schema)
    hpxml2_doc = objectify.parse(pathobj_to_str(hpxml2_file))
    hpxml2_schema.assertValid(hpxml2_doc)

    # Change the namespace of every element to use the HPXML v3 namespace
    # https://stackoverflow.com/a/51660868/11600307
    change_ns_xslt = etree.parse(str(pathlib.Path(__file__).resolve().parent / 'change_namespace.xsl'))
    hpxml3_doc = hpxml2_doc.xslt(change_ns_xslt, orig_namespace=f"'{hpxml2_ns}'", new_namespace=f"'{hpxml3_ns}'")
    root = hpxml3_doc.getroot()

    # Change version
    root.attrib['schemaVersion'] = '3.0'

    # Standardized location mapping
    location_map = {'ambient': 'outside',
                    'conditioned space': 'living space',
                    'unconditioned basement': 'basement - unconditioned',
                    'unconditioned attic': 'attic - unconditioned',
                    'unvented crawlspace': 'crawlspace - unvented',
                    'vented crawlspace': 'crawlspace - vented'}

    # Fixing project ids
    # https://github.com/hpxmlwg/hpxml/pull/197
    # This is really messy. I can see why we fixed it.

    def get_pre_post_from_building_id(building_id):
        event_type = root.xpath(
            'h:Building[h:BuildingID/@id=$bldgid]/h:ProjectStatus/h:EventType/text()',
            smart_strings=False,
            bldgid=building_id,
            **xpkw
        )
        if len(event_type) == 1:
            if event_type[0] in ('proposed workscope', 'approved workscope',
                                 'construction-period testing/daily test out',
                                 'job completion testing/final inspection', 'quality assurance/monitoring'):
                return 'post'
            elif event_type[0] in ('audit', 'preconstruction'):
                return 'pre'
            else:
                return None
        else:
            return None

    for i, project in enumerate(root.xpath('h:Project', **xpkw), 1):

        # Add the ProjectID element if it isn't there
        if not hasattr(project, 'ProjectID'):
            add_after(project, ['BuildingID'], E.ProjectID(id=f'project-{i}'))
        building_ids_by_pre_post = defaultdict(set)

        # Gather together the buildings in BuildingID and ProjectSystemIdentifiers
        building_id = project.BuildingID.attrib['id']
        building_ids_by_pre_post[get_pre_post_from_building_id(building_id)].add(building_id)
        for psi in project.xpath('h:ProjectDetails/h:ProjectSystemIdentifiers', **xpkw):
            building_id = psi.attrib.get('id')
            building_ids_by_pre_post[get_pre_post_from_building_id(building_id)].add(building_id)

        for pre_post in ('pre', 'post'):
            if len(building_ids_by_pre_post[pre_post]) == 0:
                for building_id in root.xpath('h:Building/h:BuildingID/@id', **xpkw):
                    if get_pre_post_from_building_id(building_id) == pre_post:
                        building_ids_by_pre_post[pre_post].add(building_id)

        # If there are more than one of each pre and post, throw an error
        if len(building_ids_by_pre_post['pre']) == 0:
            raise exc.HpxmlTranslationError(
                f"Project[{i}] has no references to Building nodes with an 'audit' or 'preconstruction' EventType."
            )
        elif len(building_ids_by_pre_post['pre']) > 1:
            raise exc.HpxmlTranslationError(
                f"Project[{i}] has more than one reference to Building nodes with an "
                "'audit' or 'preconstruction' EventType."
            )
        if len(building_ids_by_pre_post['post']) == 0:
            raise exc.HpxmlTranslationError(
                f"Project[{i}] has no references to Building nodes with a post retrofit EventType."
            )
        elif len(building_ids_by_pre_post['post']) > 1:
            raise exc.HpxmlTranslationError(
                f"Project[{i}] has more than one reference to Building nodes with a post retrofit EventType."
            )
        pre_building_id = building_ids_by_pre_post['pre'].pop()
        post_building_id = building_ids_by_pre_post['post'].pop()

        # Add the pre building
        project.ProjectID.addnext(E.PreBuildingID(id=pre_building_id))
        for el in root.xpath('h:Building/h:BuildingID[@id=$bldgid]/*', bldgid=pre_building_id, **xpkw):
            project.PreBuildingID.append(deepcopy(el))

        # Add the post building
        project.PreBuildingID.addnext(E.PostBuildingID(id=post_building_id))
        for el in root.xpath('h:Building/h:BuildingID[@id=$bldgid]/*', bldgid=post_building_id, **xpkw):
            project.PostBuildingID.append(deepcopy(el))

        # Move the ambiguous BuildingID to an extension
        if not hasattr(project, 'extension'):
            project.append(E.extension())
        project.extension.append(deepcopy(project.BuildingID))
        project.remove(project.BuildingID)

        # Move the ProjectSystemIdentifiers to an extension
        for psi in project.xpath('h:ProjectDetails/h:ProjectSystemIdentifiers', **xpkw):
            project.extension.append(deepcopy(psi))
            project.ProjectDetails.remove(psi)

    # Green Building Verification
    # https://github.com/hpxmlwg/hpxml/pull/66

    energy_score_els = root.xpath(
        'h:Building/h:BuildingDetails/h:BuildingSummary/h:BuildingConstruction/h:EnergyScore', **xpkw
    )
    for i, es in enumerate(energy_score_els, 1):
        bldg_details = es.getparent().getparent().getparent()
        if not hasattr(bldg_details, 'GreenBuildingVerifications'):
            add_after(
                bldg_details,
                ['BuildingSummary', 'ClimateandRiskZones'],
                E.GreenBuildingVerifications()
            )
        gbv = E.GreenBuildingVerification(
            E.SystemIdentifier(id=f'energy-score-{i}'),
            E.Type({
                'US DOE Home Energy Score': 'Home Energy Score',
                'RESNET HERS': 'HERS Index Score',
                'other': 'other'
            }[str(es.ScoreType)]),
            E.Body({
                'US DOE Home Energy Score': 'US DOE',
                'RESNET HERS': 'RESNET',
                'other': 'other'
            }[str(es.ScoreType)]),
            E.Metric(str(es.Score))
        )
        if hasattr(es, 'OtherScoreType'):
            gbv.Type.addnext(E.OtherType(str(es.OtherScoreType)))
        if hasattr(es, 'ScoreDate'):
            gbv.append(E.Year(dt.datetime.strptime(str(es.ScoreDate), '%Y-%m-%d').year))
        if hasattr(es, 'extension'):
            gbv.append(deepcopy(es.extension))
        bldg_details.GreenBuildingVerifications.append(gbv)
        es.getparent().remove(es)

    for i, prog_cert in enumerate(root.xpath('h:Project/h:ProjectDetails/h:ProgramCertificate', **xpkw), 1):
        project_details = prog_cert.getparent()
        bldg_id = project_details.getparent().PostBuildingID.attrib['id']
        bldg_details = root.xpath('h:Building[h:BuildingID/@id=$bldgid]/h:BuildingDetails', bldgid=bldg_id, **xpkw)[0]
        if not hasattr(bldg_details, 'GreenBuildingVerifications'):
            add_after(
                bldg_details,
                ['BuildingSummary', 'ClimateandRiskZones'],
                E.GreenBuildingVerifications()
            )
        gbv = E.GreenBuildingVerification(
            E.SystemIdentifier(id=f'program-certificate-{i}'),
            E.Type({
                'Home Performance with Energy Star': 'Home Performance with ENERGY STAR',
                'LEED Certified': 'LEED For Homes',
                'LEED Silver': 'LEED For Homes',
                'LEED Gold': 'LEED For Homes',
                'LEED Platinum': 'LEED For Homes',
                'other': 'other'
            }[str(prog_cert)])
        )
        if hasattr(project_details, 'CertifyingOrganization'):
            gbv.append(E.Body(str(project_details.CertifyingOrganization)))
        m = re.match(r'LEED (\w+)$', str(prog_cert))
        if m:
            gbv.append(E.Rating(m.group(1)))
        if hasattr(project_details, 'CertifyingOrganizationURL'):
            gbv.append(E.URL(str(project_details.CertifyingOrganizationURL)))
        if hasattr(project_details, 'YearCertified'):
            gbv.append(E.Year(int(project_details.YearCertified)))
        bldg_details.GreenBuildingVerifications.append(gbv)

    for i, es_home_ver in enumerate(root.xpath('h:Project/h:ProjectDetails/h:EnergyStarHomeVersion', **xpkw)):
        bldg_id = es_home_ver.getparent().getparent().PostBuildingID.attrib['id']
        bldg_details = root.xpath('h:Building[h:BuildingID/@id=$bldgid]/h:BuildingDetails', bldgid=bldg_id, **xpkw)[0]
        if not hasattr(bldg_details, 'GreenBuildingVerifications'):
            add_after(
                bldg_details,
                ['BuildingSummary', 'ClimateandRiskZones'],
                E.GreenBuildingVerifications()
            )
        gbv = E.GreenBuildingVerification(
            E.SystemIdentifier(id=f'energy-star-home-{i}'),
            E.Type('ENERGY STAR Certified Homes'),
            E.Version(str(es_home_ver))
        )
        bldg_details.GreenBuildingVerifications.append(gbv)

    for el_name in ('CertifyingOrganization', 'CertifyingOrganizationURL', 'YearCertified', 'ProgramCertificate',
                    'EnergyStarHomeVersion'):
        for el in root.xpath(f'//h:ProjectDetails/h:{el_name}', **xpkw):
            el.getparent().remove(el)

    # Addressing Inconsistencies
    # https://github.com/hpxmlwg/hpxml/pull/124

    for el in root.xpath('//h:HeatPump/h:AnnualCoolEfficiency', **xpkw):
        el.tag = f'{{{hpxml3_ns}}}AnnualCoolingEfficiency'
    for el in root.xpath('//h:HeatPump/h:AnnualHeatEfficiency', **xpkw):
        el.tag = f'{{{hpxml3_ns}}}AnnualHeatingEfficiency'

    # Replaces Measure/InstalledComponent with Measure/InstalledComponents/InstalledComponent
    for i, ic in enumerate(root.xpath('h:Project/h:ProjectDetails/h:Measures/h:Measure/h:InstalledComponent', **xpkw)):
        ms = ic.getparent()
        if not hasattr(ms, 'InstalledComponents'):
            try:
                sibling = getattr(ms, 'extension')
            except AttributeError:
                ms.append(E.InstalledComponents())
            else:
                sibling.addprevious(E.InstalledComponents())
        ms.InstalledComponents.append(deepcopy(ic))
        ms.remove(ic)

    # Replaces WeatherStation/SystemIdentifiersInfo with WeatherStation/SystemIdentifier
    for el in root.xpath('//h:WeatherStation/h:SystemIdentifiersInfo', **xpkw):
        el.tag = f'{{{hpxml3_ns}}}SystemIdentifier'

    # Renames "central air conditioning" to "central air conditioner" for CoolingSystemType
    for el in root.xpath('//h:CoolingSystem/h:CoolingSystemType', **xpkw):
        if el == 'central air conditioning':
            el._setText('central air conditioner')

    # Renames HeatPump/BackupAFUE to BackupAnnualHeatingEfficiency, accepts 0-1 instead of 1-100
    for bkupafue in root.xpath(
        'h:Building/h:BuildingDetails/h:Systems/h:HVAC/h:HVACPlant/h:HeatPump/h:BackupAFUE', **xpkw
    ):
        bkupafue.addnext(E.BackupAnnualHeatingEfficiency(
            E.Units('AFUE'),
            E.Value(f'{float(bkupafue.text) / 100}')
        ))
        bkupafue.getparent().remove(bkupafue)

    # Renames FoundationWall/BelowGradeDepth to FoundationWall/DepthBelowGrade
    for el in root.xpath('//h:FoundationWall/h:BelowGradeDepth', **xpkw):
        el.tag = f'{{{hpxml3_ns}}}DepthBelowGrade'

    # Clothes Dryer CEF
    # https://github.com/hpxmlwg/hpxml/pull/145

    for el in root.xpath('//h:ClothesDryer/h:EfficiencyFactor', **xpkw):
        el.tag = f'{{{hpxml3_ns}}}EnergyFactor'

    # Enclosure
    # https://github.com/hpxmlwg/hpxml/pull/181

    for fw in root.xpath(
        'h:Building/h:BuildingDetails/h:Enclosure/h:Foundations/h:Foundation/h:FoundationWall', **xpkw
    ):
        enclosure = fw.getparent().getparent().getparent()
        foundation = fw.getparent()

        fw.addnext(E.AttachedToFoundationWall(idref=fw.SystemIdentifier.attrib['id']))
        if not hasattr(enclosure, 'FoundationWalls'):
            add_after(
                enclosure,
                ['AirInfiltration',
                 'Attics',
                 'Foundations',
                 'Garages',
                 'Roofs',
                 'RimJoists',
                 'Walls'],
                E.FoundationWalls()
            )
        enclosure.FoundationWalls.append(deepcopy(fw))
        this_fw = enclosure.FoundationWalls.FoundationWall[-1]

        if hasattr(this_fw, 'AdjacentTo'):
            try:
                fw_boundary = location_map[str(fw.AdjacentTo)]
            except KeyError:
                fw_boundary = str(fw.AdjacentTo)  # retain unchanged location name
            try:
                boundary_v3 = {'other housing unit': E.ExteriorAdjacentTo(fw_boundary),
                               'unconditioned basement': E.InteriorAdjacentTo(fw_boundary),
                               'living space': E.InteriorAdjacentTo(fw_boundary),
                               'ground': E.ExteriorAdjacentTo(fw_boundary),
                               'crawlspace': E.InteriorAdjacentTo(fw_boundary),
                               'attic': E.InteriorAdjacentTo(fw_boundary),  # FIXME: double-check
                               'garage': E.InteriorAdjacentTo(fw_boundary),
                               'ambient': E.ExteriorAdjacentTo(fw_boundary)}[str(fw.AdjacentTo)]
                add_after(
                    this_fw,
                    ['SystemIdentifier',
                     'ExternalResource',
                     'AttachedToSpace'],
                    boundary_v3
                )
            except KeyError:
                pass
            this_fw.remove(this_fw.AdjacentTo)

        foundation.remove(fw)

    # Attics
    for bldg_const in root.xpath('h:Building/h:BuildingDetails/h:BuildingSummary/h:BuildingConstruction', **xpkw):
        if hasattr(bldg_const, 'AtticType'):
            if bldg_const.AtticType == 'vented attic':
                bldg_const.AtticType = E.AtticType(E.Attic(E.Vented(True)))
            elif bldg_const.AtticType == 'unvented attic':
                bldg_const.AtticType = E.AtticType(E.Attic(E.Vented(False)))
            elif bldg_const.AtticType == 'flat roof':
                bldg_const.AtticType = E.AtticType(E.FlatRoof())
            elif bldg_const.AtticType == 'cathedral ceiling':
                bldg_const.AtticType = E.AtticType(E.CathedralCeiling())
            elif bldg_const.AtticType == 'cape cod':
                bldg_const.AtticType = E.AtticType(E.Attic(E.CapeCod(True)))
            elif bldg_const.AtticType == 'other':
                bldg_const.AtticType = E.AtticType(E.Other())
            elif bldg_const.AtticType == 'venting unknown attic':
                bldg_const.AtticType = E.AtticType(E.Attic(E.extension(E.Vented('unknown'))))

    for i, attic in enumerate(
        root.xpath('h:Building/h:BuildingDetails/h:Enclosure/h:AtticAndRoof/h:Attics/h:Attic', **xpkw)
    ):
        enclosure = attic.getparent().getparent().getparent()
        if not hasattr(enclosure, 'Attics'):
            add_after(
                enclosure,
                ['AirInfiltration'],
                E.Attics()
            )
        this_attic = deepcopy(attic)

        if hasattr(this_attic, 'AtticType'):
            if this_attic.AtticType == 'vented attic':
                this_attic.AtticType = E.AtticType(E.Attic(E.Vented(True)))
            elif this_attic.AtticType == 'unvented attic':
                this_attic.AtticType = E.AtticType(E.Attic(E.Vented(False)))
            elif this_attic.AtticType == 'flat roof':
                this_attic.AtticType = E.AtticType(E.FlatRoof())
            elif this_attic.AtticType == 'cathedral ceiling':
                this_attic.AtticType = E.AtticType(E.CathedralCeiling())
            elif this_attic.AtticType == 'cape cod':
                this_attic.AtticType = E.AtticType(E.Attic(E.CapeCod(True)))
            elif this_attic.AtticType == 'other':
                this_attic.AtticType = E.AtticType(E.Other())
            elif this_attic.AtticType == 'venting unknown attic':
                this_attic.AtticType = E.AtticType(E.Attic(E.extension(E.Vented('unknown'))))

        # move AttachedToRoof to after VentilationRate
        if hasattr(this_attic, 'AttachedToRoof'):
            attached_to_roof = deepcopy(this_attic.AttachedToRoof)
            this_attic.remove(this_attic.AttachedToRoof)  # remove the AttachedToRoof of HPXML v2
            add_after(
                this_attic,
                ['SystemIdentifier',
                 'AttachedToSpace',
                 'AtticType',
                 'VentilationRate'],
                attached_to_roof
            )

        # find the wall with the same id and add AtticWallType = knee wall
        if hasattr(this_attic, 'AtticKneeWall'):
            knee_wall_id = this_attic.AtticKneeWall.attrib['idref']
            knee_wall = root.xpath(
                'h:Building/h:BuildingDetails/h:Enclosure/h:Walls/h:Wall[h:SystemIdentifier/@id=$sysid]',
                sysid=knee_wall_id, **xpkw)[0]
            add_after(
                knee_wall,
                ['SystemIdentifier',
                 'ExteriorAdjacentTo',
                 'InteriorAdjacentTo'],
                E.AtticWallType('knee wall')
            )

        # create a FrameFloor adjacent to the attic and assign the area below to Area
        # and then copy AtticFloorInsulation over to Insulation of the frame floor
        if hasattr(this_attic, 'AtticFloorInsulation'):
            if not hasattr(enclosure, 'FrameFloors'):
                add_before(
                    enclosure,
                    ['Slabs',
                     'Windows',
                     'Skylights',
                     'Doors',
                     'extension'],
                    E.FrameFloors()
                )
            attic_floor_el = E.FrameFloor(
                E.SystemIdentifier(id=f'attic-floor-{i}'),
                E.InteriorAdjacentTo('attic'),
            )
            if hasattr(this_attic, 'Area'):
                attic_floor_el.append(E.Area(float(this_attic.Area)))
            attic_floor_insulation = deepcopy(this_attic.AtticFloorInsulation)
            attic_floor_insulation.tag = f'{{{hpxml3_ns}}}Insulation'
            attic_floor_el.append(attic_floor_insulation)
            enclosure.FrameFloors.append(attic_floor_el)

        # find the roof whose InteriorAdjacentTo is attic and then copy it to Insulation of the roof
        # add insulation to v2 Roofs and these roofs will be converted into hpxml v3 later
        if hasattr(this_attic, 'AtticRoofInsulation'):
            roof_insulation = deepcopy(this_attic.AtticRoofInsulation)
            roof_insulation.tag = f'{{{hpxml3_ns}}}Insulation'
            roof_idref = this_attic.AttachedToRoof.attrib['idref']
            roof_attached_to_this_attic = root.xpath(
                'h:Building/h:BuildingDetails/h:Enclosure/h:AtticAndRoof/h:Roofs/h:Roof[h:SystemIdentifier/@id=$sysid]',
                sysid=roof_idref, **xpkw)[0]
            add_before(
                roof_attached_to_this_attic,
                ['extension'],
                roof_insulation
            )

        # move Rafters to v2 Roofs and these roofs will be converted into hpxml v3 later
        if hasattr(this_attic, 'Rafters'):
            rafters = deepcopy(this_attic.Rafters)
            roof_idref = this_attic.AttachedToRoof.attrib['idref']
            roof_attached_to_this_attic = root.xpath(
                'h:Building/h:BuildingDetails/h:Enclosure/h:AtticAndRoof/h:Roofs/h:Roof[h:SystemIdentifier/@id=$sysid]',
                sysid=roof_idref, **xpkw)[0]
            add_after(
                roof_attached_to_this_attic,
                ['SystemIdentifier',
                 'ExternalResource',
                 'AttachedToSpace',
                 'RoofColor',
                 'SolarAbsorptance',
                 'Emittance'],
                rafters
            )

        el_not_in_v3 = ['ExteriorAdjacentTo',
                        'InteriorAdjacentTo',
                        'AtticKneeWall',
                        'AtticFloorInsulation',
                        'AtticRoofInsulation',
                        'Area',
                        'Rafters']
        for el in el_not_in_v3:
            if hasattr(this_attic, el):
                this_attic.remove(this_attic[el])

        enclosure.Attics.append(this_attic)

    # Roofs
    for roof in root.xpath('h:Building/h:BuildingDetails/h:Enclosure/h:AtticAndRoof/h:Roofs/h:Roof', **xpkw):
        enclosure = roof.getparent().getparent().getparent()
        if not hasattr(enclosure, 'Roofs'):
            add_after(
                enclosure,
                ['AirInfiltration',
                 'Attics',
                 'Foundations',
                 'Garages'],
                E.Roofs()
            )
        enclosure.Roofs.append(deepcopy(roof))
        this_roof = enclosure.Roofs.Roof[-1]

        if hasattr(roof, 'RoofArea'):
            add_after(
                this_roof,
                ['SystemIdentifier',
                 'ExternalResource',
                 'AttachedToSpace',
                 'InteriorAdjacentTo'],
                E.Area(float(roof.RoofArea))
            )
            this_roof.remove(this_roof.RoofArea)

        if hasattr(roof, 'RoofType'):
            roof_type = str(roof.RoofType)
            this_roof.remove(this_roof.RoofType)  # remove the RoofType of HPXML v2
            add_after(
                this_roof,
                ['SystemIdentifier',
                 'ExternalResource',
                 'AttachedToSpace',
                 'InteriorAdjacentTo',
                 'Area',
                 'Orientation',
                 'Azimuth'],
                E.RoofType(roof_type)
            )

    # remove AtticAndRoof after rearranging all attics and roofs
    for enclosure in root.xpath('h:Building/h:BuildingDetails/h:Enclosure', **xpkw):
        try:
            enclosure.remove(enclosure.AtticAndRoof)
        except AttributeError:
            pass

    # Frame Floors
    for ff in root.xpath('h:Building/h:BuildingDetails/h:Enclosure/h:Foundations/h:Foundation/h:FrameFloor', **xpkw):
        enclosure = ff.getparent().getparent().getparent()
        foundation = ff.getparent()

        el_attached_to_ff = E.AttachedToFrameFloor(idref=ff.SystemIdentifier.attrib['id'])
        if hasattr(foundation, 'AttachedToFoundationWall'):
            foundation.AttachedToFoundationWall.addnext(el_attached_to_ff)  # make the element order valid
        else:
            ff.addnext(el_attached_to_ff)
        if not hasattr(enclosure, 'FrameFloors'):
            add_before(
                enclosure,
                ['Slabs',
                 'Windows',
                 'Skylights',
                 'Doors',
                 'extension'],
                E.FrameFloors()
            )
        this_ff = deepcopy(ff)
        enclosure.FrameFloors.append(this_ff)
        foundation.remove(ff)

    # Slabs
    for slab in root.xpath('h:Building/h:BuildingDetails/h:Enclosure/h:Foundations/h:Foundation/h:Slab', **xpkw):
        enclosure = slab.getparent().getparent().getparent()
        foundation = slab.getparent()

        slab.addnext(E.AttachedToSlab(idref=slab.SystemIdentifier.attrib['id']))
        if not hasattr(enclosure, 'Slabs'):
            add_before(
                enclosure,
                ['Windows',
                 'Skylights',
                 'Doors',
                 'extension'],
                E.Slabs()
            )
        enclosure.Slabs.append(deepcopy(slab))
        foundation.remove(slab)

    # Remove 'Insulation/InsulationLocation'
    for insulation_location in root.xpath('//h:Insulation/h:InsulationLocation', **xpkw):
        # Insulation location to be layer-specific
        insulation = insulation_location.getparent()
        if hasattr(insulation, 'Layer'):
            for layer in insulation.Layer:
                if layer.InstallationType == 'continuous':
                    layer.InstallationType._setText(f'continuous - {str(insulation.InsulationLocation)}')
        insulation.remove(insulation.InsulationLocation)

    # Windows and Skylights
    for i, win in enumerate(root.xpath('//h:Window|//h:Skylight', **xpkw)):
        if hasattr(win, 'VisibleTransmittance'):
            vis_trans = float(win.VisibleTransmittance)
            win.remove(win.VisibleTransmittance)  # remove VisibleTransmittance of HPXML v2
            add_after(
                win,
                ['SystemIdentifier',
                 'ExternalResource',
                 'Area',
                 'Quantity',
                 'Azimuth',
                 'Orientation',
                 'FrameType',
                 'GlassLayers',
                 'GlassType',
                 'GasFill',
                 'Condition',
                 'UFactor',
                 'SHGC'],
                E.VisibleTransmittance(vis_trans)
            )
        if hasattr(win, 'ExteriorShading'):
            ext_shade = str(win.ExteriorShading)
            win.remove(win.ExteriorShading)  # remove ExteriorShading of HPXML v2
            add_after(
                win,
                ['SystemIdentifier',
                 'ExternalResource',
                 'Area',
                 'Quantity',
                 'Azimuth',
                 'Orientation',
                 'FrameType',
                 'GlassLayers',
                 'GlassType',
                 'GasFill',
                 'Condition',
                 'UFactor',
                 'SHGC',
                 'VisibleTransmittance',
                 'NFRCCertified',
                 'ThirdPartyCertification',
                 'WindowFilm'],
                E.ExteriorShading(
                    E.SystemIdentifier(id=f'exterior-shading-{i}'),
                    E.Type(ext_shade)
                )
            )
        if hasattr(win, 'Treatments'):
            if win.Treatments in ['shading', 'solar screen']:
                treatment_shade = E.ExteriorShading(
                    E.SystemIdentifier(id=f'treatment-shading-{i}'),
                )
                if win.Treatments == 'solar screen':
                    treatment_shade.append(E.Type('solar screens'))
                add_after(
                    win,
                    ['SystemIdentifier',
                     'ExternalResource',
                     'Area',
                     'Quantity',
                     'Azimuth',
                     'Orientation',
                     'FrameType',
                     'GlassLayers',
                     'GlassType',
                     'GasFill',
                     'Condition',
                     'UFactor',
                     'SHGC',
                     'VisibleTransmittance',
                     'NFRCCertified',
                     'ThirdPartyCertification',
                     'WindowFilm'],
                    treatment_shade
                )
            elif win.Treatments == 'window film':
                add_after(
                    win,
                    ['SystemIdentifier',
                     'ExternalResource',
                     'Area',
                     'Quantity',
                     'Azimuth',
                     'Orientation',
                     'FrameType',
                     'GlassLayers',
                     'GlassType',
                     'GasFill',
                     'Condition',
                     'UFactor',
                     'SHGC',
                     'VisibleTransmittance',
                     'NFRCCertified',
                     'ThirdPartyCertification'],
                    E.WindowFilm(
                        E.SystemIdentifier(id=f'window-film-{i}')
                    )
                )
            win.remove(win.Treatments)
        if hasattr(win, 'InteriorShading'):
            cache_interior_shading_type = str(win.InteriorShading)
            win.InteriorShading.clear()
            win.InteriorShading.append(E.SystemIdentifier(id=f'interior-shading-{i}'))
            win.InteriorShading.append(E.Type(cache_interior_shading_type))
        if hasattr(win, 'InteriorShadingFactor'):
            # handles a case where `InteriorShadingFactor` is specified without `InteriorShading`
            if not hasattr(win, 'InteriorShading'):
                win.InteriorShadingFactor.addnext(E.InteriorShading(
                    E.SystemIdentifier(id=f'interior-shading-{i}')
                ))
            win.InteriorShading.extend([
                E.SummerShadingCoefficient(float(win.InteriorShadingFactor)),
                E.WinterShadingCoefficient(float(win.InteriorShadingFactor))
            ])
            win.remove(win.InteriorShadingFactor)
        if hasattr(win, 'MovableInsulationRValue'):
            add_after(
                win,
                ['SystemIdentifier',
                 'ExternalResource',
                 'Area',
                 'Quantity',
                 'Azimuth',
                 'Orientation',
                 'FrameType',
                 'GlassLayers',
                 'GlassType',
                 'GasFill',
                 'Condition',
                 'UFactor',
                 'SHGC',
                 'VisibleTransmittance',
                 'NFRCCertified',
                 'ThirdPartyCertification',
                 'WindowFilm',
                 'ExteriorShading',
                 'InteriorShading',
                 'StormWindow'],
                E.MoveableInsulation(
                    E.SystemIdentifier(id=f'moveable-insulation-{i}'),
                    E.RValue(float(win.MovableInsulationRValue))
                )
            )
            win.remove(win.MovableInsulationRValue)
        if hasattr(win, 'GlassLayers'):
            if win.GlassLayers in ['single-paned with low-e storms', 'single-paned with storms']:
                storm_window = E.StormWindow(
                    E.SystemIdentifier(id=f'storm-window-{i}')
                )
                if win.GlassLayers == 'single-paned with low-e storms':
                    storm_window.append(E.GlassType('low-e'))
                win.GlassLayers._setText('single-pane')
                add_after(
                    win,
                    ['SystemIdentifier',
                     'ExternalResource',
                     'Area',
                     'Quantity',
                     'Azimuth',
                     'Orientation',
                     'FrameType',
                     'GlassLayers',
                     'GlassType',
                     'GasFill',
                     'Condition',
                     'UFactor',
                     'SHGC',
                     'VisibleTransmittance',
                     'NFRCCertified',
                     'ThirdPartyCertification',
                     'WindowFilm',
                     'ExteriorShading',
                     'InteriorShading'],
                    storm_window
                )

    # Standardize Locations
    # https://github.com/hpxmlwg/hpxml/pull/156

    for el in root.xpath('//h:InteriorAdjacentTo|//h:ExteriorAdjacentTo|//h:DuctLocation|//h:HVACPlant/h:*/h:UnitLocation|//h:WaterHeatingSystem/h:Location|//h:Measure/h:Location', **xpkw):  # noqa E501
        try:
            el._setText(location_map[el.text])
        except (KeyError, AttributeError):
            pass

    # Lighting Fraction Improvements
    # https://github.com/hpxmlwg/hpxml/pull/165

    ltgidx = 0
    for ltgfracs in root.xpath('h:Building/h:BuildingDetails/h:Lighting/h:LightingFractions', **xpkw):
        ltg = ltgfracs.getparent()
        for ltgfrac in ltgfracs.getchildren():
            ltgidx += 1
            ltggroup = E.LightingGroup(
                E.SystemIdentifier(id=f'lighting-fraction-{ltgidx}'),
                E.FractionofUnitsInLocation(ltgfrac.text),
                E.LightingType()
            )
            if ltgfrac.tag == f'{{{hpxml3_ns}}}FractionIncandescent':
                ltggroup.LightingType.append(E.Incandescent())
            elif ltgfrac.tag == f'{{{hpxml3_ns}}}FractionCFL':
                ltggroup.LightingType.append(E.CompactFluorescent())
            elif ltgfrac.tag == f'{{{hpxml3_ns}}}FractionLFL':
                ltggroup.LightingType.append(E.FluorescentTube())
            elif ltgfrac.tag == f'{{{hpxml3_ns}}}FractionLED':
                ltggroup.LightingType.append(E.LightEmittingDiode())
            ltg.append(ltggroup)
        ltg.remove(ltgfracs)

    # Deprecated items
    # https://github.com/hpxmlwg/hpxml/pull/167

    # Removes WaterHeaterInsulation/Pipe; use HotWaterDistribution/PipeInsulation instead
    for i, pipe in enumerate(root.xpath('//h:WaterHeaterInsulation/h:Pipe', **xpkw), 1):
        waterheating = pipe.getparent().getparent().getparent()
        waterheatingsystem = pipe.getparent().getparent()
        waterheatingsystem_idref = str(waterheatingsystem.SystemIdentifier.attrib['id'])
        try:
            hw_dist = waterheating.xpath('h:HotWaterDistribution[h:AttachedToWaterHeatingSystem/@idref=$sysid]',
                                         sysid=waterheatingsystem_idref, **xpkw)[0]
            add_after(
                hw_dist,
                ['SystemIdentifier',
                 'ExternalResource',
                 'AttachedToWaterHeatingSystem',
                 'SystemType'],
                E.PipeInsulation(
                    E.PipeRValue(float(pipe.PipeRValue))
                )
            )
        except IndexError:  # handles when there is no attached hot water distribution system
            add_after(
                waterheating,
                ['WaterHeatingSystem',
                 'WaterHeatingControl'],
                E.HotWaterDistribution(
                    E.SystemIdentifier(id=f'hotwater-distribution-{i}'),
                    E.AttachedToWaterHeatingSystem(idref=waterheatingsystem_idref),
                    E.PipeInsulation(
                        E.PipeRValue(float(pipe.PipeRValue))
                    )
                )
            )
        waterheaterinsualtion = pipe.getparent()
        waterheaterinsualtion.remove(pipe)
        if waterheaterinsualtion.countchildren() == 0:
            waterheaterinsualtion.getparent().remove(waterheaterinsualtion)

    # Removes PoolPump/HoursPerDay; use PoolPump/PumpSpeed/HoursPerDay instead
    for poolpump_hour in root.xpath('//h:PoolPump/h:HoursPerDay', **xpkw):
        poolpump = poolpump_hour.getparent()
        if not hasattr(poolpump, 'PumpSpeed'):
            poolpump_hour.addnext(E.PumpSpeed(E.HoursPerDay(float(poolpump_hour))))
        else:
            poolpump.PumpSpeed.append(E.HoursPerDay(float(poolpump_hour)))
        poolpump.remove(poolpump_hour)

    # Removes "indoor water " (note extra trailing space) enumeration from WaterType
    for watertype in root.xpath('//h:WaterType', **xpkw):
        if watertype == 'indoor water ':
            watertype._setText(str(watertype).rstrip())

    # Adds desuperheater flexibility
    # https://github.com/hpxmlwg/hpxml/pull/184

    for el in root.xpath('//h:WaterHeatingSystem/h:RelatedHeatingSystem', **xpkw):
        el.tag = f'{{{hpxml3_ns}}}RelatedHVACSystem'
    for el in root.xpath('//h:WaterHeatingSystem/h:HasGeothermalDesuperheater', **xpkw):
        el.tag = f'{{{hpxml3_ns}}}UsesDesuperheater'

    # TODO: Allow insulation location to be layer-specific
    # https://github.com/hpxmlwg/hpxml/pull/188

    # TODO: Window/Skylight Interior Shading Fraction
    # https://github.com/hpxmlwg/hpxml/pull/189

    # TODO: Window sub-components
    # https://github.com/hpxmlwg/hpxml/pull/202

    # TODO: Clarify PV inverter efficiency value
    # https://github.com/hpxmlwg/hpxml/pull/207

    # TODO: updating BPI-2101 enums in GreenBuildingVerification/Type
    # https://github.com/hpxmlwg/hpxml/pull/210

    # Write out new file
    hpxml3_doc.write(pathobj_to_str(hpxml3_file), pretty_print=True, encoding='utf-8')
    hpxml3_schema.assertValid(hpxml3_doc)
