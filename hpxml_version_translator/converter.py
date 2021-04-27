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
                sibling = getattr(parent_el, sibling_name)
            except AttributeError:
                continue
            else:
                sibling.addnext(el_to_add)
                return
        parent_el.insert(0, el_to_add)

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

    # Fixing project ids
    # https://github.com/hpxmlwg/hpxml/pull/197
    # This is really messy. I can see why we fixed it.

    def get_event_type_from_building_id(building_id):
        event_type = root.xpath(
            'h:Building[h:BuildingID/@id=$bldgid]/h:ProjectStatus/h:EventType/text()',
            smart_strings=False,
            bldgid=building_id,
            **xpkw
        )
        if len(event_type) == 1:
            return event_type[0]
        else:
            return None

    for i, project in enumerate(root.xpath('h:Project', **xpkw), 1):

        # Add the ProjectID element if it isn't there
        if not hasattr(project, 'ProjectID'):
            add_after(project, ['BuildingID'], E.ProjectID(id=f'project-{i}'))
        building_ids_by_event_type = defaultdict(set)

        # Gather together the buildings in BuildingID and ProjectSystemIdentifiers
        building_id = project.BuildingID.attrib['id']
        building_ids_by_event_type[get_event_type_from_building_id(building_id)].add(building_id)
        for psi in project.xpath('h:ProjectDetails/h:ProjectSystemIdentifiers', **xpkw):
            building_id = psi.attrib['id']
            building_ids_by_event_type[get_event_type_from_building_id(building_id)].add(building_id)

        # Separate the buildings into pre and post retrofit buildings by their EventType
        pre_building_ids = set()
        for event_type in ('audit', 'preconstruction'):
            pre_building_ids.update(building_ids_by_event_type[event_type])
        post_building_ids = set()
        for event_type in ('proposed workscope', 'approved workscope', 'construction-period testing/daily test out',
                           'job completion testing/final inspection', 'quality assurance/monitoring'):
            post_building_ids.update(building_ids_by_event_type[event_type])

        # If there are more than one of each pre and post, throw an error
        if len(pre_building_ids) == 0:
            raise exc.HpxmlTranslationError(
                f"Project[{i}] has no references to Building nodes with an 'audit' or 'preconstruction' EventType."
            )
        elif len(pre_building_ids) > 1:
            raise exc.HpxmlTranslationError(
                f"Project[{i}] has more than one reference to Building nodes with an "
                "'audit' or 'preconstruction' EventType."
            )
        if len(post_building_ids) == 0:
            raise exc.HpxmlTranslationError(
                f"Project[{i}] has no references to Building nodes with a post retrofit EventType."
            )
        elif len(post_building_ids) > 1:
            raise exc.HpxmlTranslationError(
                f"Project[{i}] has more than one reference to Building nodes with a post retrofit EventType."
            )
        pre_building_id = pre_building_ids.pop()
        post_building_id = post_building_ids.pop()

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
    for i, ms in enumerate(root.xpath('h:Project/h:ProjectDetails/h:Measures/h:Measure', **xpkw)):
        if not hasattr(ms, 'InstalledComponents'):
            try:
                sibling = getattr(ms, 'extension')
            except AttributeError:
                ms.append(E.InstalledComponents())
            else:
                sibling.addprevious(E.InstalledComponents())
        ic = E.InstalledComponent(id=str(ms.InstalledComponent.attrib['id']))
        ms.InstalledComponents.append(ic)
        ms.remove(ms.InstalledComponent)

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

    for i, fw in enumerate(root.xpath(
        'h:Building/h:BuildingDetails/h:Enclosure/h:Foundations/h:Foundation/h:FoundationWall', **xpkw
    )):
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
        this_fw = enclosure.FoundationWalls.FoundationWall[i]

        try:
            boundary_v3 = {'other housing unit': E.ExteriorAdjacentTo(str(fw.AdjacentTo)),
                           # FUTURE: change it when issue #3 is addressed
                           'unconditioned basement': E.InteriorAdjacentTo('basement - unconditioned'),
                           'living space': E.InteriorAdjacentTo(str(fw.AdjacentTo)),
                           'ground': E.ExteriorAdjacentTo(str(fw.AdjacentTo)),
                           'crawlspace': E.InteriorAdjacentTo(str(fw.AdjacentTo)),
                           'attic': E.InteriorAdjacentTo(str(fw.AdjacentTo)),  # FIXME: double-check
                           'garage': E.InteriorAdjacentTo(str(fw.AdjacentTo)),
                           # FUTURE: change it when issue #3 is addressed
                           'ambient': E.ExteriorAdjacentTo('outside')}[fw.AdjacentTo]
            add_after(
                this_fw,
                ['SystemIdentifier',
                 'ExternalResource',
                 'AttachedToSpace'],
                boundary_v3
            )
        except KeyError:
            pass

        if hasattr(this_fw, 'AdjacentTo'):
            this_fw.remove(this_fw.AdjacentTo)

        foundation.remove(fw)

    # Attics
    for i, attic in enumerate(root.xpath(
        'h:Building/h:BuildingDetails/h:Enclosure/h:AtticAndRoof/h:Attics/h:Attic', **xpkw
    )):
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
            add_after(
                this_attic,
                ['SystemIdentifier',
                 'AttachedToSpace',
                 'AtticType',
                 'VentilationRate'],
                attached_to_roof
            )
            this_attic.remove(this_attic.AttachedToRoof[0])  # remove the AttachedToRoof of HPXML v2
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
            attic_floor_insulation = deepcopy(this_attic.AtticFloorInsulation)
            attic_floor_insulation.tag = f'{{{hpxml3_ns}}}Insulation'
            enclosure.append(
                E.FrameFloors(
                    E.FrameFloor(
                        E.SystemIdentifier(id='attic_floor'),
                        E.InteriorAdjacentTo('attic'),
                    )
                )
            )
            if hasattr(this_attic, 'Area'):
                enclosure.FrameFloors.FrameFloor.append(E.Area(float(this_attic.Area)))
            enclosure.FrameFloors.FrameFloor.append(attic_floor_insulation)
        # find the roof whose InteriorAdjacentTo is attic and then copy it to Insulation of the roof
        # FIXME: add insulation to v2 Roofs and these roofs will be converted into hpxml v3 later
        if hasattr(this_attic, 'AtticRoofInsulation'):
            roof_insulation = deepcopy(this_attic.AtticRoofInsulation)
            roof_insulation.tag = f'{{{hpxml3_ns}}}Insulation'
            for i, rf in enumerate(root.xpath(
                'h:Building/h:BuildingDetails/h:Enclosure/h:AtticAndRoof/h:Roofs/h:Roof', **xpkw
            )):
                add_after(
                    rf,
                    ['Pitch',
                     'RoofArea',
                     'RadiantBarrier',
                     'RadiantBarrierLocation'],
                    roof_insulation
                )
        # move Rafters to Roof
        # FIXME: move Rafters to v2 Roofs and these roofs will be converted into hpxml v3 later
        if hasattr(this_attic, 'Rafters'):
            rafters = deepcopy(this_attic.Rafters)
            for i, rf in enumerate(root.xpath(
                'h:Building/h:BuildingDetails/h:Enclosure/h:AtticAndRoof/h:Roofs/h:Roof', **xpkw
            )):
                add_after(
                    rf,
                    ['RoofColor',
                     'SolarAbsorptance',
                     'Emittance'],
                    rafters
                )

        el_not_in_v3 = [
            'ExteriorAdjacentTo',
            'InteriorAdjacentTo',
            'AtticKneeWall',
            'AtticFloorInsulation',
            'AtticRoofInsulation',
            'Area',
            'Rafters'
        ]
        for el in el_not_in_v3:
            if hasattr(this_attic, el):
                this_attic.remove(this_attic[el])

        enclosure.Attics.append(this_attic)

    # Roofs
    for i, roof in enumerate(root.xpath(
        'h:Building/h:BuildingDetails/h:Enclosure/h:AtticAndRoof/h:Roofs/h:Roof', **xpkw
    )):
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

        if hasattr(roof, 'RoofArea'):
            add_after(
                enclosure.Roofs.Roof,
                ['SystemIdentifier',
                 'ExternalResource',
                 'AttachedToSpace',
                 'InteriorAdjacentTo'],
                E.Area(float(roof.RoofArea))
            )
            enclosure.Roofs.Roof.remove(enclosure.Roofs.Roof.RoofArea)

        if hasattr(roof, 'RoofType'):
            add_after(
                enclosure.Roofs.Roof,
                ['SystemIdentifier',
                 'ExternalResource',
                 'AttachedToSpace',
                 'InteriorAdjacentTo',
                 'Area',
                 'Orientation',
                 'Azimuth'],
                E.RoofType(str(roof.RoofType))
            )
            enclosure.Roofs.Roof.remove(enclosure.Roofs.Roof.RoofType[1])  # remove the RoofType of HPXML v2

    # remove AtticAndRoof after rearranging all attics and roofs
    try:
        root.Building.BuildingDetails.Enclosure.remove(root.Building.BuildingDetails.Enclosure.AtticAndRoof)
    except AttributeError:
        pass

    # Frame Floors
    for i, ff in enumerate(root.xpath(
        'h:Building/h:BuildingDetails/h:Enclosure/h:Foundations/h:Foundation/h:FrameFloor', **xpkw
    )):
        enclosure = ff.getparent().getparent().getparent()
        foundation = ff.getparent()

        ff.addnext(E.AttachedToFrameFloor(idref=ff.SystemIdentifier.attrib['id']))
        if not hasattr(enclosure, 'FrameFloors'):
            add_after(
                enclosure,
                ['AirInfiltration',
                 'Attics',
                 'Foundations',
                 'Garages',
                 'Roofs',
                 'RimJoists',
                 'Walls',
                 'FoundationWalls'],
                E.FrameFloors()
            )
        this_ff = deepcopy(ff)
        # Preserve insulation location for each insulation layer
        if hasattr(this_ff.Insulation, 'InsulationLocation') and hasattr(this_ff.Insulation, 'Layer'):
            for i, layer in enumerate(this_ff.Insulation.Layer):
                if layer.InstallationType == 'continuous':
                    layer.InstallationType._setText(f'continuous - {str(this_ff.Insulation.InsulationLocation)}')

        enclosure.FrameFloors.append(this_ff)
        foundation.remove(ff)

    # Slabs
    for i, slab in enumerate(root.xpath(
        'h:Building/h:BuildingDetails/h:Enclosure/h:Foundations/h:Foundation/h:Slab', **xpkw
    )):
        enclosure = slab.getparent().getparent().getparent()
        foundation = slab.getparent()

        slab.addnext(E.AttachedToSlab(idref=slab.SystemIdentifier.attrib['id']))
        if not hasattr(enclosure, 'Slabs'):
            add_after(
                enclosure,
                ['AirInfiltration',
                 'Attics',
                 'Foundations',
                 'Garages',
                 'Roofs',
                 'RimJoists',
                 'Walls',
                 'FoundationWalls',
                 'FrameFloors'],
                E.Slabs()
            )
        enclosure.Slabs.append(deepcopy(slab))
        foundation.remove(slab)

    # Remove 'Insulation/InsulationLocation'
    # TODO: Use it for other enclosure types
    for ins_loc in root.xpath('//h:Insulation/h:InsulationLocation', **xpkw):
        ins = ins_loc.getparent()
        ins.remove(ins.InsulationLocation)

    # TODO: Standardize Locations
    # https://github.com/hpxmlwg/hpxml/pull/156

    # TODO: Lighting Fraction Improvements
    # https://github.com/hpxmlwg/hpxml/pull/165

    # TODO: Deprecated items
    # https://github.com/hpxmlwg/hpxml/pull/167

    # TODO: Adds desuperheater flexibility
    # https://github.com/hpxmlwg/hpxml/pull/184

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
