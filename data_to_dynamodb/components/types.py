from enum import Enum
import datetime


class Source(Enum):
    RS = 'RS'               # Rechtspraak
    LI = 'LI'               # Legal Intelligence
    LIDO = 'LIDO'           # Linked Data Overheid
    CJEU = 'CJEU'           # Court of Justice of the European Union
    ECHR = 'ECHR'           # European Court of Human Rights


class DocType(Enum):
    DEC = 'DEC'             # case decision
    OPI = 'OPI'             # case opinion
    C_CIT = 'C-CIT'         # case citation
    L_CIT = 'L-CIT'         # legislation citation
    DOM = 'DOM'             # associated domain


def validate_source(source):
    if source == '':
        return source
    elif not isinstance(source, Source):
        print('Invalid source. Source should be of type Source.')
        return source
    return source.value


def validate_doctype(doctype):
    if doctype == '':
        return doctype
    elif not isinstance(doctype, DocType):
        print('Invalid doc_type. Doc_type should be of type DocType.')
        return doctype
    return doctype.value


def validate_date(date):
    try:
        if date != '':
            datetime.datetime.strptime(date, '%Y-%m-%d')
    except ValueError:
        print('Invalid date. Date should be of format YYYY-MM-DD.')
    return date

