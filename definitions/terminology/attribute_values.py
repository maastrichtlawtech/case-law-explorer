from enum import Enum


# --- data attributes ---

class Domain(Enum):
    """
    Original RS terminology: https://uitspraken.rechtspraak.nl/ > 'Uitgebreid zoeken' > 'Rechtsgebieden'
    Original LI terminology: https://www.legalintelligence.com/search?q=*&fq=Jurisdiction_HF%3A1%7C010_Nederland%7C010_Rechtspraak > 'Rechtsgebied'
    """
    # Bestuursrecht and subdomains
    BESTUURSRECHT = 'Bestuursrecht'
    AMBTENARENRECHT = 'Ambtenarenrecht'
    BELASTINGRECHT = 'Belastingrecht'
    BESTUURSPROCESRECHT = 'Bestuursprocesrecht'
    BESTUURSSTRAFRECHT = 'Bestuursstrafrecht'
    EUROPEES_BESTUURSRECHT = 'Europees bestuursrecht'
    MEDEDINGINGSRECHT = 'Mededingingsrecht'
    OMGEVINGSRECHT = 'Omgevingsrecht'
    SOCIALEZEKERHEIDSRECHT = 'Socialezekerheidsrecht'
    VREEMDELINGENRECHT = 'Vreemdelingenrecht'
    ONDERWIJS_STUDIEFINANCIERING = 'Onderwijs/Studiefinanciering'
    RUIMTELIJK_BESTUURSRECHT_MILIEURECHT_ENERGIERECHT = 'Ruimtelijk Bestuursrecht/Milieurecht/Energierecht'

    # Civielrecht and subdomains
    CIVIELRECHT = 'Civiel recht'
    AANBESTEDINGSRECHT = 'Aanbestedingsrecht'
    ARBEIDSRECHT = 'Arbeidsrecht'
    BURGERLIJK_PROCESRECHT = 'Burgerlijk procesrecht'
    EUROPEES_CIVIEL_RECHT = 'Europees civiel recht'
    GOEDERENRECHT = 'Goederenrecht'
    INSOLVENTIERECHT = 'Insolventierecht'
    INTELLECTUEEL_EIGENDOMSRECHT = 'Intellectueel-eigendomsrecht'
    INTERNATIONAAL_PRIVAATRECHT = 'Internationaal privaatrecht'
    ONDERNEMINGSRECHT = 'Ondernemingsrecht'
    PERSONEN_EN_FAMILIENRECHT = 'Personen- en familierecht'
    VERBINTENISSENRECHT = 'Verbintenissenrecht'
    BOUWRECHT = 'Bouwrecht'
    BURGERLIJK_RECHT = 'Burgerlijk recht'
    GEZONDHEIDSRECHT = 'Gezondheidsrecht'
    HUURRECHT_WOONRECHT = 'Huurrecht/Woonrecht'
    VERVOER_VERKEERSRECHT = 'Vervoer/Verkeersrecht'
    VERZEKERINGSRECHT = 'Verzekeringsrecht'
    TELECOM_ICT_MEDIARECHT = 'Telecom/ICT/Mediarecht'

    # Internationaal publiekrecht and subdomains
    INTERNATIONAAL_PUBLIEKRECHT = 'Internationaal publiekrecht'
    MENSENRECHTEN = 'Mensenrechten'
    VOLKENRECHT = 'Volkenrecht'

    # Strafrecht and subdomains
    STRAFRECHT = 'Strafrecht'
    EUROPEES_STRAFRECHT = 'Europees strafrecht'
    INTERNATIONAAL_STRAFRECHT = 'Internationaal strafrecht'
    MATERIEEL_STRAFRECHT = 'Materieel strafrecht'
    PENITENTIAIR_STRAFRECHT = 'Penitentiair strafrecht'
    STRAFPROCESRECHT = 'Strafprocesrecht'

    # Uncategorized domains
    ALGEMEEN_OVERIG_NIED_GELABELD = 'Algemeen/Overig/Niet-gelabeld'
    BANK_EN_EFFECTENRECHT = 'Bank- en effectenrecht'
    GEMEENSCHAPSRECHT_EU = 'Gemeenschapsrecht EU'
    BUITENLANDS_RELIGIEUS_RECHT = 'Buitenlands Recht/Religieus recht'


class Instance(Enum):
    HOGE_RAAD = 'Hoge Raad'
    RAAD_VAN_STATE = 'Raad van State'
    RAAD_VAN_BEROEP = 'Centrale Raad van Beroep'
    COLLEGE_VAN_BEROEP = 'College van Beroep voor het bedrijfsleven'
    GH_AMS = 'Gerechtshof Amsterdam'
    GH_AL = 'Gerechtshof Arnhem-Leeuwarden'
    GH_HAAG = 'Gerechtshof \'s-Gravenhage'
    GH_BOSCH = 'Gerechtshof \'s-Hertogenbosch'
    GERECHTSHOVEN = [GH_AMS, GH_AL, GH_HAAG, GH_BOSCH]
    RB_AMS = 'Rechtbank Amsterdam'
    RB_HAAG = 'Rechtbank \'s-Gravenhage'
    RB_GE = 'Rechtbank Gelderland'
    RB_LI = 'Rechtbank Limburg'
    RB_MN = 'Rechtbank Midden-Nederland'
    RB_NH = 'Rechtbank Noord-Holland'
    RB_NN = 'Rechtbank Noord-Nederland'
    RB_OB = 'Rechtbank Oost-Brabant'
    RB_OV = 'Rechtbank Overijssel'
    RB_RO = 'Rechtbank Rotterdam'
    RB_ZWB = 'Rechtbank Zeeland-West-Brabant'
    RECHTBANKEN = [RB_AMS, RB_HAAG, RB_GE, RB_LI, RB_MN, RB_NH, RB_NN, RB_OB, RB_OV, RB_RO, RB_ZWB]
    CH_SM = 'Constitutioneel Hof Sint Maarten'
    GHJ_ACSMBSES = 'Gemeenschappelijk Hof van Justitie van Aruba, Curaçao, Sint Maarten en van Bonaire, Sint Eustatius en Saba'
    GA_ACSMBSES = 'Gerecht in Ambtenarenzaken van Aruba, Curaçao, Sint Maarten en van Bonaire, Sint Eustatius en Saba'
    GEA_A = 'Gerecht in Eerste Aanleg van Aruba'
    GEA_BSES = 'Gerecht in eerste aanleg van Bonaire, Sint Eustatius en Saba'
    GEA_C = 'Gerecht in eerste aanleg van Curaçao'
    GEA_SM = 'Gerecht in eerste aanleg van Sint Maarten'
    RBA_ACSMBSES = 'Raad van Beroep in Ambtenarenzaken van Aruba, Curaçao, Sint Maarten en van Bonaire, Sint Eustatius en Saba'
    RBB_ACSMBSES = 'Raad van Beroep voor Belastingzaken van Aruba, Curaçao, Sint Maarten en van Bonaire, Sint Eustatius en Saba'
    ANDERE = [CH_SM, GHJ_ACSMBSES, GA_ACSMBSES, GEA_A, GEA_BSES, GEA_C, GEA_SM, RBA_ACSMBSES, RBB_ACSMBSES]


class InstanceComponent(Enum):
    GERECHTSHOF = 'Gerechtshof'
    RECHTBANK = 'Rechtbank'
    S_GRAVENHAGE = "'s-Gravenhage"
    AMSTERDAM = 'Amsterdam'
    S_HERTOGENBOSCH = "'s-Hertogenbosch"
    ARNHEM_LEEUWARDEN = 'Arnhem-Leeuwarden'
    GELDERLAND = 'Gelderland'
    LIMBURG = 'Limburg'
    MIDDEN_NEDERLAND = 'Midden-Nederland'
    NOORD_HOLLAND = 'Noord-Holland'
    NOORD_NEDERLAND = 'Noord-Nederland'
    OOST_BRABANT = 'Oost-Brabant'
    OVERIJSSEL = 'Overijssel'
    ROTTERDAM = 'Rotterdam'
    ZEELAND = 'Zeeland-West-Brabant'


class Jurisdiction(Enum):
    NL = 'NL'  # used for country and language
    # to be extended


class Source(Enum):
    RECHTSPRAAK = 'Rechtspraak'
    # to be extended


# --- DynamoDB schema keys ---

class DataSource(Enum):
    RS = 'RS'               # Rechtspraak
    ECHR = 'ECHR'           # European Court of Human Rights
    EURLEX = 'EURLEX'       # Court of Justice of the European Union


class DocType(Enum):
    DEC = 'DEC'             # case decision
    OPI = 'OPI'             # case opinion


class ItemType(Enum):
    DATA = 'DATA'
    DOM = 'DOM'             # associated domain
    DOM_LI = 'DOM-LI'
