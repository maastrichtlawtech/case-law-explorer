from definitions.terminology.field_names import ECLI, ECLI_DECISION, ECLI_OPINION, RS_SUBJECT, LI_LAW_AREA, RS_RELATION, \
    LIDO_JURISPRUDENTIE, RS_REFERENCES, LIDO_ARTIKEL_TITLE, RS_DATE
from .types import Source, DocType, ItemType


KEY_SEP = '_'               # used to separate compound key values
key_sdd = 'SourceDocDate'   # name of secondary sort key
LI = '_li'                  # suffix of attributes from LI data
SET_SEP = '; '              # used to separate set items in string


def row_processor_rs_cases(row, pk, sk):
    """
    turns csv row (1 RS case) into item(s) for DynamoDB table according to this schema
    :param row: dict representation of csv row with RS case attributes
    :return: list of dict representation of items in schema format
    """
    put_items = []
    update_items = []
    update_set_items = []
    # split set attributes (domain, case citations, legislation citations)
    if RS_SUBJECT in row:
        for val in row[RS_SUBJECT].split(SET_SEP):
            put_items.append({
                pk: row[ECLI],
                sk: ItemType.DOM.value + KEY_SEP + val,
                key_sdd: Source.RS.value + KEY_SEP + DocType.DEC.value + KEY_SEP + row[RS_DATE],
                RS_SUBJECT[:-1]: val
            })
    for attribute in [RS_RELATION, RS_REFERENCES, RS_SUBJECT]:
        if attribute in row:
            update_set_items.append({
                pk: row[ECLI],
                sk: ItemType.DATA.value,
                attribute: set(row[attribute].split(SET_SEP))
            })
            row.pop(attribute)
    put_items.append({
        sk: ItemType.DATA.value,
        key_sdd: Source.RS.value + KEY_SEP + DocType.DEC.value + KEY_SEP + row[RS_DATE],
        **row
    })
    return put_items, update_items, update_set_items


def row_processor_rs_opinions(row, pk, sk):
    put_items = []
    update_items = []
    update_set_items = []
    if RS_SUBJECT in row:
        for val in row[RS_SUBJECT].split(SET_SEP):
            put_items.append({
                pk: row[ECLI],
                sk: ItemType.DOM.value + KEY_SEP + val,
                key_sdd: Source.RS.value + KEY_SEP + DocType.OPI.value + KEY_SEP + row[RS_DATE],
                RS_SUBJECT[:-1]: val
            })
    # split set attributes (domain, case citations, legislation citations)
    for attribute in [RS_RELATION, RS_REFERENCES, RS_SUBJECT]:
        if attribute in row:
            update_set_items.append({
                pk: row[ECLI],
                sk: ItemType.DATA.value,
                attribute: set(row[attribute].split(SET_SEP))
            })
            row.pop(attribute)
    put_items.append({
        sk: ItemType.DATA.value,
        key_sdd: Source.RS.value + KEY_SEP + DocType.OPI.value + KEY_SEP + row[RS_DATE],
        **row
    })
    if ECLI_DECISION in row:
        update_items.append({
            pk: row[ECLI_DECISION],
            sk: ItemType.DATA.value,
            ECLI_OPINION: row[ECLI]
        })
    return put_items, update_items, update_set_items


def row_processor_li_cases(row, pk, sk):
    put_items = []
    update_items = []
    update_set_items = []
    row_li = dict()
    for key in row.keys():
        if not key == ECLI:
            row_li[key + LI] = row[key]
    if LI_LAW_AREA in row:
        for val in row[LI_LAW_AREA].split(SET_SEP):
            put_items.append({
                pk: row[ECLI],
                sk: ItemType.DOM_LI.value + KEY_SEP + val,
                key_sdd: Source.RS.value + KEY_SEP + DocType.DEC.value + KEY_SEP + row[RS_DATE],
                LI_LAW_AREA[:-1] + LI: val
            })
        update_set_items.append({
            pk: row[ECLI],
            sk: ItemType.DATA.value,
            LI_LAW_AREA + LI: set(row[LI_LAW_AREA].split(SET_SEP))
        })
        row_li.pop(LI_LAW_AREA + LI)
    update_items.append({
        pk: row[ECLI],
        sk: ItemType.DATA.value,
        key_sdd: Source.RS.value + KEY_SEP + DocType.DEC.value + KEY_SEP + row[RS_DATE],
        **row_li
    })
    return put_items, update_items, update_set_items

# @TODO: replace attribute names with global definition
def row_processor_c_citations(row, pk, sk):
    put_items = []
    update_items = []
    update_set_items = []
    if row['keep1'] == 'True':
        update_set_items = [{
            pk: row[ECLI],
            sk: ItemType.DATA.value,
            'cites': {row[LIDO_JURISPRUDENTIE]}
        }, {
            pk: row[LIDO_JURISPRUDENTIE],
            sk: ItemType.DATA.value,
            'cited_by': {row[ECLI]}
        }]
    return put_items, update_items, update_set_items


def row_processor_l_citations(row, pk, sk):
    put_items = []
    update_items = []
    update_set_items = [{
        pk: row[ECLI],
        sk: ItemType.DATA.value,
        'legal_provisions': {row[LIDO_ARTIKEL_TITLE]}
    }]
    return put_items, update_items, update_set_items
