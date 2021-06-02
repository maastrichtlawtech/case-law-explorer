from enum import Enum


class Source(Enum):
    RS = 'RS'               # Rechtspraak
    CJEU = 'CJEU'           # Court of Justice of the European Union
    ECHR = 'ECHR'           # European Court of Human Rights


class ItemType(Enum):
    DATA = 'DATA'
    DOM = 'DOM'             # associated domain
    DOM_LI = 'DOM-LI'


class DocType(Enum):
    DEC = 'DEC'             # case decision
    OPI = 'OPI'             # case opinion
