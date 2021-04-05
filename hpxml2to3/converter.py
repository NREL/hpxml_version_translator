from copy import deepcopy
import datetime as dt
from lxml import etree, objectify
import pathlib


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

    print(energy_score_els)

    # TODO: Addressing Inconsistencies
    # https://github.com/hpxmlwg/hpxml/pull/124

    # TODO: Clothes Dryer CEF
    # https://github.com/hpxmlwg/hpxml/pull/145

    # TODO: Standardize Locations
    # https://github.com/hpxmlwg/hpxml/pull/156

    # TODO: Lighting Fraction Improvements
    # https://github.com/hpxmlwg/hpxml/pull/165

    # TODO: Deprecated items
    # https://github.com/hpxmlwg/hpxml/pull/167

    # TODO: Enclosure
    # https://github.com/hpxmlwg/hpxml/pull/181

    # TODO: Adds desuperheater flexibility
    # https://github.com/hpxmlwg/hpxml/pull/184

    # TODO: Allow insulation location to be layer-specific
    # https://github.com/hpxmlwg/hpxml/pull/188

    # TODO: Window/Skylight Interior Shading Fraction
    # https://github.com/hpxmlwg/hpxml/pull/189

    # TODO: Fixing project ids
    # https://github.com/hpxmlwg/hpxml/pull/197

    # TODO: Window sub-components
    # https://github.com/hpxmlwg/hpxml/pull/202

    # TODO: Clarify PV inverter efficiency value
    # https://github.com/hpxmlwg/hpxml/pull/207

    # TODO: updating BPI-2101 enums in GreenBuildingVerification/Type
    # https://github.com/hpxmlwg/hpxml/pull/210

    # Write out new file
    hpxml3_doc.write(pathobj_to_str(hpxml3_file), pretty_print=True, encoding='utf-8')
    hpxml3_schema.assertValid(hpxml3_doc)
