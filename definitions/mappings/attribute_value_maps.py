from definitions.terminology.attribute_values import Domain, Jurisdiction

MAP_LI_DOMAINS = {
    'Algemeen': {Domain.ALGEMEEN_OVERIG_NIED_GELABELD.value},
    'Arbeids/Sociaal Recht': {Domain.CIVIELRECHT.value, Domain.ARBEIDSRECHT.value},
    'Bank- en effectenrecht': {Domain.ALGEMEEN_OVERIG_NIED_GELABELD.value, Domain.BANK_EN_EFFECTENRECHT.value},
    'Belastingrecht': {Domain.BESTUURSRECHT.value, Domain.BELASTINGRECHT.value},
    'Bouwrecht': {Domain.CIVIELRECHT.value, Domain.VERBINTENISSENRECHT.value, Domain.BOUWRECHT.value, Domain.AANBESTEDINGSRECHT.value},
    'Buitenlands Recht/Religieus recht': {Domain.ALGEMEEN_OVERIG_NIED_GELABELD.value, Domain.BUITENLANDS_RELIGIEUS_RECHT.value},
    'Burgerlijk recht': {Domain.CIVIELRECHT.value, Domain.VERBINTENISSENRECHT.value, Domain.BURGERLIJK_RECHT.value, Domain.GOEDERENRECHT.value},
    'Burgerlijke rechtsvordering': {Domain.CIVIELRECHT.value, Domain.BURGERLIJK_PROCESRECHT.value},
    'Faillissementsrecht': {Domain.CIVIELRECHT.value, Domain.INSOLVENTIERECHT.value},
    'Gemeenschapsrecht EU': {Domain.ALGEMEEN_OVERIG_NIED_GELABELD.value, Domain.GEMEENSCHAPSRECHT_EU.value},
    'Gezondheidsrecht': {Domain.CIVIELRECHT.value, Domain.VERBINTENISSENRECHT.value, Domain.GEZONDHEIDSRECHT.value, Domain.BESTUURSRECHT.value},
    'Huurrecht/Woonrecht': {Domain.CIVIELRECHT.value, Domain.VERBINTENISSENRECHT.value, Domain.HUURRECHT_WOONRECHT.value, Domain.BESTUURSRECHT.value},
    'Intellectuele eigendom': {Domain.CIVIELRECHT.value, Domain.INTELLECTUEEL_EIGENDOMSRECHT.value},
    'Internationaal Privaatrecht/IPR': {Domain.CIVIELRECHT.value, Domain.INTERNATIONAAL_PRIVAATRECHT.value},
    'Internationaal Publiekrecht (niet EU)': {Domain.INTERNATIONAAL_PUBLIEKRECHT.value},
    'Mededinging': {Domain.CIVIELRECHT.value, Domain.BESTUURSRECHT.value, Domain.MEDEDINGINGSRECHT.value},
    'Nationaliteitsrecht/Vreemdelingenrecht': {Domain.BESTUURSRECHT.value, Domain.VREEMDELINGENRECHT.value},
    'Onbekend': {Domain.ALGEMEEN_OVERIG_NIED_GELABELD.value},
    'Ondernemingsrecht': {Domain.CIVIELRECHT.value, Domain.ONDERNEMINGSRECHT.value},
    'Onderwijs/Studiefinanciering': {Domain.BESTUURSRECHT.value, Domain.ONDERWIJS_STUDIEFINANCIERING.value},
    'Personen- en Familierecht': {Domain.CIVIELRECHT.value, Domain.PERSONEN_EN_FAMILIENRECHT.value},
    'Ruimtelijk Bestuursrecht/Milieurecht/Energierecht': {Domain.BESTUURSRECHT.value, Domain.RUIMTELIJK_BESTUURSRECHT_MILIEURECHT_ENERGIERECHT.value},
    'Staats- en Bestuursrecht': {Domain.BESTUURSRECHT.value},
    'Strafrecht/Strafvordering': {Domain.STRAFRECHT.value},
    'Telecom/ICT/Mediarecht': {Domain.CIVIELRECHT.value, Domain.TELECOM_ICT_MEDIARECHT.value},
    'Verbintenissenrecht': {Domain.CIVIELRECHT.value, Domain.VERBINTENISSENRECHT.value},
    'Vervoer/Verkeersrecht': {Domain.CIVIELRECHT.value, Domain.VERBINTENISSENRECHT.value, Domain.VERVOER_VERKEERSRECHT.value, Domain.STRAFRECHT.value},
    'Verzekeringsrecht': {Domain.CIVIELRECHT.value, Domain.VERBINTENISSENRECHT.value, Domain.VERZEKERINGSRECHT.value}
}

S_GRAVENHAGE = "'s-Gravenhage"
RECHTBANK = 'Rechtbank'

MAP_INSTANCE = {
    "'s-Gravenhage": S_GRAVENHAGE,
    "'s Gravenhage": S_GRAVENHAGE,
    'Den Haag': S_GRAVENHAGE,
    'Sector kanton Rechtbank': RECHTBANK,
    'Rechtbank': RECHTBANK
}

MAP_JURISDICTION = {
    'NL': Jurisdiction.NL.value,
    'Nederland': Jurisdiction.NL.value
}