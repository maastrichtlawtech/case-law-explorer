import json
import re
import zipfile
from lxml import etree

from lido.config import *

def task_unzip_bwbidlist():
    with zipfile.ZipFile(FILE_BWB_IDS_ZIP, 'r') as zip_ref:
        zip_ref.extract("BWBIdList.xml", DIR_DATA_BWB)

def task_bwbidlist_xml_to_json():
    output = []

    NS = {"NS1": "http://schemas.overheid.nl/bwbidservice"}

    root = etree.parse(FILE_BWB_IDS_XML)
    regelingLijst = root.find('NS1:RegelingInfoLijst', namespaces=NS)
    for regeling in regelingLijst.iterfind('NS1:RegelingInfo', namespaces=NS):
        bwb_id = regeling.find('NS1:BWBId', namespaces=NS).text
        titel_officieel = regeling.find('NS1:OfficieleTitel', namespaces=NS).text

        citeer_titels = [
            titel.find('NS1:titel', namespaces=NS).text
            for titel
            in regeling
                .find('NS1:CiteertitelLijst', namespaces=NS)
                .iterfind('NS1:Citeertitel', namespaces=NS)
        ]
        afkortingen = [
            afkorting.text
            for afkorting
            in regeling
                .find('NS1:AfkortingLijst', namespaces=NS)
                .iterfind('NS1:Afkorting', namespaces=NS)
        ]
        titels_niet_officieel = [
            titel.text
            for titel
            in regeling
                .find('NS1:NietOfficieleTitelLijst', namespaces=NS)
                .iterfind('NS1:NietOfficieleTitel', namespaces=NS)
        ]

        titels = [titel_officieel] + citeer_titels + afkortingen + titels_niet_officieel

        # limit length and remove some unwanted chars, as per xslt file
        titels = [
            re.sub(r'\s+', ' ',
                re.sub(r'^(\s|[.,;:])+', '', titel)
            )
            for titel in titels
            if titel and len(titel) > 0 and len(titel) < 2500
        ]

        output.append([bwb_id, titels])

    with open(FILE_BWB_IDS_JSON, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
