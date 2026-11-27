"""Rich legislation metadata & structured article-text ingestion (Track B).

Fetches official public metadata and article-structured full text for:
  1. EU CELLAR (`scheme = 'celex'`):
       - `https://publications.europa.eu/resource/celex/{CELEX}` with
         `Accept: application/xml;notice=tree` (falling back to `notice=object`)
         for official title, short title, document date, entry into force,
         in-force status, ELI, EuroVoc subjects, legal basis, and amending acts.
       - Same URL with `Accept: application/xhtml+xml` + `Accept-Language: eng`
         for structured `<div id="art_...">` / `<p class="...ti-art...">` articles.
  2. Dutch BWB (`scheme = 'bwb'`):
       - `https://zoekservice.overheid.nl/sru/Search?operation=searchRetrieve&version=1.2&x-connection=BWB&maximumRecords=1&query=dcterms.identifier=={BWBID} AND overheidbwb.geldigheidsdatum={TODAY}`
         (falling back without date for repealed statutes, setting `in_force = False`)
         for official title, `rechtsgebied` / `overheidsdomein` subjects, validity
         dates, and `locatie_toestand` consolidated XML URL.
       - `locatie_toestand` XML for `<artikel>` / `<kop>` / `<lid>` structured texts
         with `label-id` matching `cle_v2.legal_provision.bwb_label_id`.
  3. ECHR Convention & Protocols (`scheme = 'coe_treaty'`, `identifier = '005'`):
       - Structured Council of Europe Convention + Protocol article headings and
         official article texts so `/law/treaty/ECHR` serves complete articles.

Writes idempotent JSONL records (`legislation_enrichment.jsonl`) that both
`enrichment_sync_etl` (on `db-dev`) and `etl-promoter` (on production) replay
via `load_enrichment_artifact(conn, path)`.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html as html_lib
import json
import logging
import os
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

log = logging.getLogger(__name__)

SCHEMA = "cle_v2"
EXTRACTOR_VERSION = "legislation_enrichment/1.0.0"
USER_AGENT = "CaseLawExplorer/1.0 (https://caselawexplorer.tech)"

CELLAR_RESOURCE_URL = "https://publications.europa.eu/resource/celex/{celex}"
BWB_SRU_URL = (
    "https://zoekservice.overheid.nl/sru/Search"
    "?operation=searchRetrieve&version=1.2&x-connection=BWB&maximumRecords=1&query={query}"
)


@dataclass(frozen=True)
class ArticleProvision:
    article_label: str
    element_type: str = "artikel"
    title: Optional[str] = None
    text: str = ""
    bwb_label_id: Optional[int] = None


@dataclass(frozen=True)
class LegislationEnrichment:
    scheme: str
    identifier: str
    metadata_source: str
    title: Optional[str] = None
    short_title: Optional[str] = None
    document_type: Optional[str] = None
    date_document: Optional[str] = None
    date_entry_into_force: Optional[str] = None
    in_force: Optional[bool] = None
    eli: Optional[str] = None
    subjects: Tuple[str, ...] = ()
    legal_basis: Tuple[str, ...] = ()
    amending_acts: Tuple[str, ...] = ()
    articles: Tuple[ArticleProvision, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scheme": self.scheme,
            "identifier": self.identifier,
            "metadata_source": self.metadata_source,
            "title": self.title,
            "short_title": self.short_title,
            "document_type": self.document_type,
            "date_document": self.date_document,
            "date_entry_into_force": self.date_entry_into_force,
            "in_force": self.in_force,
            "eli": self.eli,
            "subjects": list(self.subjects),
            "legal_basis": list(self.legal_basis),
            "amending_acts": list(self.amending_acts),
            "articles": [asdict(a) for a in self.articles],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LegislationEnrichment":
        articles = tuple(
            ArticleProvision(
                article_label=str(a["article_label"]),
                element_type=str(a.get("element_type") or "artikel"),
                title=a.get("title") or None,
                text=str(a.get("text") or ""),
                bwb_label_id=int(a["bwb_label_id"]) if a.get("bwb_label_id") is not None else None,
            )
            for a in (data.get("articles") or ())
            if a.get("article_label")
        )
        return cls(
            scheme=str(data["scheme"]),
            identifier=str(data["identifier"]),
            metadata_source=str(data.get("metadata_source") or "unknown"),
            title=data.get("title") or None,
            short_title=data.get("short_title") or None,
            document_type=data.get("document_type") or None,
            date_document=data.get("date_document") or None,
            date_entry_into_force=data.get("date_entry_into_force") or None,
            in_force=data.get("in_force") if isinstance(data.get("in_force"), bool) else None,
            eli=data.get("eli") or None,
            subjects=tuple(str(s) for s in (data.get("subjects") or ()) if s),
            legal_basis=tuple(str(s) for s in (data.get("legal_basis") or ()) if s),
            amending_acts=tuple(str(s) for s in (data.get("amending_acts") or ()) if s),
            articles=articles,
        )


def _clean_ws(text: Optional[str]) -> str:
    if not text:
        return ""
    return re.sub(r"[ \t\r\f\v]+", " ", text).strip()


def _clean_multiline(text: Optional[str]) -> str:
    if not text:
        return ""
    lines = [_clean_ws(line) for line in text.splitlines()]
    out: List[str] = []
    for line in lines:
        if line:
            out.append(line)
    return "\n".join(out)


def _iso_date(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    m = re.match(r"^\s*(\d{4}-\d{2}-\d{2})", raw)
    return m.group(1) if m else None


def _strip_tags(fragment: str) -> str:
    text = re.sub(r"<(?:br|p|div|li|tr)\b[^>]*>", "\n", fragment, flags=re.IGNORECASE)
    text = re.sub(r"</(?:p|div|li|tr|h[1-6])>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return _clean_multiline(html_lib.unescape(text))


# ---------------------------------------------------------------------------
# 1. EU CELLAR XML notice + XHTML article parsers
# ---------------------------------------------------------------------------

def _child_value(parent: Optional[ET.Element], tag: str) -> Optional[str]:
    if parent is None:
        return None
    el = parent.find(tag)
    if el is None:
        return None
    val = el.find("VALUE")
    raw = val.text if val is not None and val.text else el.text
    return _clean_ws(raw) or None


def _extract_celex_links(work: Optional[ET.Element], tags: Sequence[str]) -> Tuple[str, ...]:
    if work is None:
        return ()
    seen: List[str] = []
    for tag in tags:
        for el in work.findall(tag):
            found = None
            for sameas in el.findall("SAMEAS"):
                uri = sameas.find("URI")
                if uri is not None and _child_value(uri, "TYPE") == "celex":
                    found = _child_value(uri, "IDENTIFIER")
                    break
            if not found:
                pref = _child_value(el, "PREFLABEL") or _child_value(el, "IDENTIFIER")
                found = pref
            if found and found not in seen:
                seen.append(found)
    return tuple(seen[:50])


def parse_cellar_notice_xml(celex: str, xml_bytes: bytes) -> LegislationEnrichment:
    """Parse EU CELLAR `notice=tree` or `notice=object` XML into LegislationEnrichment."""
    root = ET.fromstring(xml_bytes)
    work = root.find("WORK")
    expr = root.find("EXPRESSION")

    title = _child_value(expr, "EXPRESSION_TITLE")
    if title:
        title = re.sub(r"#[^#]*$", "", title).strip() or None
    short_title = _child_value(expr, "EXPRESSION_TITLE_SHORT")
    date_doc = _iso_date(_child_value(work, "WORK_DATE_DOCUMENT"))
    date_eif = _iso_date(_child_value(work, "RESOURCE_LEGAL_DATE_ENTRY-INTO-FORCE"))
    eli = _child_value(work, "RESOURCE_LEGAL_ELI")

    raw_in_force = _child_value(work, "RESOURCE_LEGAL_IN-FORCE")
    in_force: Optional[bool] = None
    if raw_in_force is not None:
        if raw_in_force.lower() == "true":
            in_force = True
        elif raw_in_force.lower() == "false":
            in_force = False

    subjects: List[str] = []
    if work is not None:
        for ev in work.findall("WORK_IS_ABOUT_CONCEPT_EUROVOC"):
            for pref in ev.iter("PREFLABEL"):
                lbl = _clean_ws(pref.text)
                if lbl and lbl not in subjects:
                    subjects.append(lbl)
        if not subjects:
            for sm in work.findall("RESOURCE_LEGAL_IS_ABOUT_SUBJECT-MATTER"):
                for pref in sm.iter("PREFLABEL"):
                    lbl = _clean_ws(pref.text)
                    if lbl and lbl not in subjects:
                        subjects.append(lbl)

    legal_basis = _extract_celex_links(
        work,
        ("RESOURCE_LEGAL_BASED_ON_CONCEPT_TREATY", "RESOURCE_LEGAL_BASED_ON_RESOURCE_LEGAL"),
    )
    amending_acts = _extract_celex_links(
        work,
        (
            "RESOURCE_LEGAL_AMENDED_BY_RESOURCE_LEGAL",
            "RESOURCE_LEGAL_AMENDMENT_PROPOSED_BY_RESOURCE_LEGAL",
        ),
    )

    return LegislationEnrichment(
        scheme="celex",
        identifier=celex.upper(),
        metadata_source="cellar_branch",
        title=title[:1000] if title else None,
        short_title=short_title[:300] if short_title else None,
        date_document=date_doc,
        date_entry_into_force=date_eif,
        in_force=in_force,
        eli=eli,
        subjects=tuple(subjects[:25]),
        legal_basis=legal_basis,
        amending_acts=amending_acts,
    )


_ELI_ART_DIV_RE = re.compile(
    r'<div\b[^>]*\bid="(?:art_|ART_)([0-9]+[a-zA-Z0-9._-]*)"[^>]*>(.*?)(?=<div\b[^>]*\bid="(?:art_|ART_|enc_|fnp_|rct_|cpt_)|</body>|$)',
    re.IGNORECASE | re.DOTALL,
)
_TI_ART_RE = re.compile(
    r'<p\b[^>]*\bclass="[^"]*ti-art[^"]*"[^>]*>(.*?)</p>(.*?)(?=<p\b[^>]*\bclass="[^"]*ti-art[^"]*"|</body>|$)',
    re.IGNORECASE | re.DOTALL,
)
_STI_ART_RE = re.compile(r'<p\b[^>]*\bclass="[^"]*sti-art[^"]*"[^>]*>(.*?)</p>', re.IGNORECASE | re.DOTALL)
_ART_NUM_RE = re.compile(r"\bArticle\s+([0-9]+[a-zA-Z]?(?:\s*[a-z])?)\b", re.IGNORECASE)


def parse_cellar_xhtml_articles(html_text: str, max_articles: int = 500) -> List[ArticleProvision]:
    """Extract structured articles from EUR-Lex / CELLAR XHTML."""
    if not html_text:
        return []

    articles: List[ArticleProvision] = []
    seen: set = set()

    # Modern OJ / ELI XHTML structure (`<div id="art_1" class="eli-subdivision">`)
    for m in _ELI_ART_DIV_RE.finditer(html_text):
        raw_id = m.group(1)
        if "." in raw_id:
            continue  # skip sub-anchors like art_1.tit_1
        label = raw_id.replace("_", " ").strip()
        if label.lower() in seen:
            continue
        block = m.group(2)
        sti_m = _STI_ART_RE.search(block)
        art_title = _strip_tags(sti_m.group(1)) if sti_m else None
        body = _strip_tags(block)
        if not body:
            continue
        seen.add(label.lower())
        articles.append(
            ArticleProvision(
                article_label=label,
                element_type="artikel",
                title=art_title[:300] if art_title else None,
                text=body[:12000],
            )
        )
        if len(articles) >= max_articles:
            return articles

    if articles:
        return articles

    # Older EUR-Lex XHTML fallback (`<p class="ti-art">Article 1</p>`)
    for m in _TI_ART_RE.finditer(html_text):
        heading = _strip_tags(m.group(1))
        num_m = _ART_NUM_RE.search(heading)
        label = num_m.group(1).strip() if num_m else heading[:40]
        if not label or label.lower() in seen:
            continue
        block = m.group(2)
        sti_m = _STI_ART_RE.search(block)
        art_title = _strip_tags(sti_m.group(1)) if sti_m else None
        body = _strip_tags(block)
        if not body:
            continue
        seen.add(label.lower())
        articles.append(
            ArticleProvision(
                article_label=label,
                element_type="artikel",
                title=art_title[:300] if art_title else None,
                text=body[:12000],
            )
        )
        if len(articles) >= max_articles:
            break

    return articles


# ---------------------------------------------------------------------------
# 2. Dutch BWB SRU + consolidated toestand XML parsers
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BwbSruMetadata:
    bwb_id: str
    title: Optional[str]
    subjects: Tuple[str, ...]
    start_date: Optional[str]
    end_date: Optional[str]
    in_force: bool
    toestand_url: Optional[str]


def parse_bwb_sru_xml(
    bwb_id: str, xml_bytes: bytes, *, today: Optional[dt.date] = None
) -> Optional[BwbSruMetadata]:
    """Parse Dutch BWB SRU response for official title, subjects, validity, and XML URL."""
    root = ET.fromstring(xml_bytes)
    today_iso = (today or dt.date.today()).isoformat()

    num_records = 0
    title: Optional[str] = None
    subjects: List[str] = []
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    toestand_url: Optional[str] = None

    for el in root.iter():
        tag = el.tag.split("}")[-1]
        text = _clean_ws(el.text)
        if not text:
            continue
        if tag == "numberOfRecords":
            try:
                num_records = int(text)
            except ValueError:
                pass
        elif tag == "title" and title is None:
            title = text
        elif tag in ("rechtsgebied", "overheidsdomein") and text not in subjects:
            subjects.append(text)
        elif tag == "geldigheidsperiode_startdatum" and start_date is None:
            start_date = _iso_date(text)
        elif tag == "geldigheidsperiode_einddatum" and end_date is None:
            end_date = _iso_date(text)
        elif tag == "locatie_toestand" and toestand_url is None:
            toestand_url = text

    if num_records == 0 and toestand_url is None and title is None:
        return None

    in_force = end_date is None or end_date == "9999-12-31" or end_date >= today_iso
    return BwbSruMetadata(
        bwb_id=bwb_id.upper(),
        title=title,
        subjects=tuple(subjects[:20]),
        start_date=start_date,
        end_date=end_date,
        in_force=in_force,
        toestand_url=toestand_url,
    )


def parse_bwb_toestand_xml(xml_bytes: bytes, max_articles: int = 1000) -> List[ArticleProvision]:
    """Parse BWB consolidated `toestand` XML `<artikel>` elements."""
    root = ET.fromstring(xml_bytes)
    articles: List[ArticleProvision] = []
    seen: set = set()

    for el in root.iter():
        if el.tag.split("}")[-1] != "artikel":
            continue
        kop = None
        for child in el:
            if child.tag.split("}")[-1] == "kop":
                kop = child
                break
        nr_text = None
        titel_text = None
        if kop is not None:
            for c in kop:
                ctag = c.tag.split("}")[-1]
                if ctag == "nr" and c.text:
                    nr_text = _clean_ws("".join(c.itertext()))
                elif ctag == "titel" and c.text:
                    titel_text = _clean_ws("".join(c.itertext()))
        if not nr_text:
            raw_lbl = el.attrib.get("label") or ""
            m = re.search(r"([0-9][0-9a-zA-Z.:-]*)", raw_lbl)
            nr_text = m.group(1) if m else None
        if not nr_text or nr_text.lower() in seen:
            continue

        # Collect body paragraphs / <lid> blocks excluding <kop>
        parts: List[str] = []
        for child in el:
            ctag = child.tag.split("}")[-1]
            if ctag == "kop":
                continue
            chunk = _clean_multiline("".join(child.itertext()))
            if chunk:
                parts.append(chunk)
        body = "\n".join(parts).strip()
        if not body:
            continue

        raw_lid = el.attrib.get("label-id")
        bwb_label_id = int(raw_lid) if raw_lid and raw_lid.isdigit() else None
        seen.add(nr_text.lower())
        articles.append(
            ArticleProvision(
                article_label=nr_text,
                element_type="artikel",
                title=titel_text[:300] if titel_text else None,
                text=body[:12000],
                bwb_label_id=bwb_label_id,
            )
        )
        if len(articles) >= max_articles:
            break

    return articles


# ---------------------------------------------------------------------------
# 3. Official ECHR Convention & Protocols structured articles
# ---------------------------------------------------------------------------

_ECHR_CORE_ARTICLES: Tuple[Tuple[str, str, str], ...] = (
    ("1", "Obligation to respect Human Rights",
     "The High Contracting Parties shall secure to everyone within their jurisdiction the rights and freedoms defined in Section I of this Convention."),
    ("2", "Right to life",
     "1. Everyone's right to life shall be protected by law. No one shall be deprived of his life intentionally save in the execution of a sentence of a court following his conviction of a crime for which this penalty is provided by law.\n2. Deprivation of life shall not be regarded as inflicted in contravention of this Article when it results from the use of force which is no more than absolutely necessary: (a) in defence of any person from unlawful violence; (b) in order to effect a lawful arrest or to prevent the escape of a person lawfully detained; (c) in action lawfully taken for the purpose of quelling a riot or insurrection."),
    ("3", "Prohibition of torture",
     "No one shall be subjected to torture or to inhuman or degrading treatment or punishment."),
    ("4", "Prohibition of slavery and forced labour",
     "1. No one shall be held in slavery or servitude.\n2. No one shall be required to perform forced or compulsory labour."),
    ("5", "Right to liberty and security",
     "1. Everyone has the right to liberty and security of person. No one shall be deprived of his liberty save in the cases prescribed by Article 5(1)(a)-(f) and in accordance with a procedure prescribed by law.\n2. Everyone who is arrested shall be informed promptly, in a language which he understands, of the reasons for his arrest and of any charge against him.\n3. Everyone arrested or detained in accordance with paragraph 1(c) shall be brought promptly before a judge and shall be entitled to trial within a reasonable time or to release pending trial.\n4. Everyone who is deprived of his liberty by arrest or detention shall be entitled to take proceedings by which the lawfulness of his detention shall be decided speedily by a court.\n5. Everyone who has been the victim of arrest or detention in contravention of this Article shall have an enforceable right to compensation."),
    ("6", "Right to a fair trial",
     "1. In the determination of his civil rights and obligations or of any criminal charge against him, everyone is entitled to a fair and public hearing within a reasonable time by an independent and impartial tribunal established by law.\n2. Everyone charged with a criminal offence shall be presumed innocent until proved guilty according to law.\n3. Everyone charged with a criminal offence has the minimum rights to be informed promptly of the accusation, to have adequate time and facilities for defence, to defend himself or have legal assistance, to examine witnesses, and to have free assistance of an interpreter."),
    ("7", "No punishment without law",
     "1. No one shall be held guilty of any criminal offence on account of any act or omission which did not constitute a criminal offence under national or international law at the time when it was committed. Nor shall a heavier penalty be imposed than the one that was applicable at the time the criminal offence was committed."),
    ("8", "Right to respect for private and family life",
     "1. Everyone has the right to respect for his private and family life, his home and his correspondence.\n2. There shall be no interference by a public authority with the exercise of this right except such as is in accordance with the law and is necessary in a democratic society in the interests of national security, public safety or the economic well-being of the country, for the prevention of disorder or crime, for the protection of health or morals, or for the protection of the rights and freedoms of others."),
    ("9", "Freedom of thought, conscience and religion",
     "1. Everyone has the right to freedom of thought, conscience and religion; this right includes freedom to change his religion or belief and freedom, either alone or in community with others and in public or private, to manifest his religion or belief, in worship, teaching, practice and observance.\n2. Freedom to manifest one's religion or beliefs shall be subject only to such limitations as are prescribed by law and are necessary in a democratic society."),
    ("10", "Freedom of expression",
     "1. Everyone has the right to freedom of expression. This right shall include freedom to hold opinions and to receive and impart information and ideas without interference by public authority and regardless of frontiers.\n2. The exercise of these freedoms, since it carries with it duties and responsibilities, may be subject to such formalities, conditions, restrictions or penalties as are prescribed by law and are necessary in a democratic society."),
    ("11", "Freedom of assembly and association",
     "1. Everyone has the right to freedom of peaceful assembly and to freedom of association with others, including the right to form and to join trade unions for the protection of his interests.\n2. No restrictions shall be placed on the exercise of these rights other than such as are prescribed by law and are necessary in a democratic society."),
    ("12", "Right to marry",
     "Men and women of marriageable age have the right to marry and to found a family, according to the national laws governing the exercise of this right."),
    ("13", "Right to an effective remedy",
     "Everyone whose rights and freedoms as set forth in this Convention are violated shall have an effective remedy before a national authority notwithstanding that the violation has been committed by persons acting in an official capacity."),
    ("14", "Prohibition of discrimination",
     "The enjoyment of the rights and freedoms set forth in this Convention shall be secured without discrimination on any ground such as sex, race, colour, language, religion, political or other opinion, national or social origin, association with a national minority, property, birth or other status."),
    ("15", "Derogation in time of emergency",
     "1. In time of war or other public emergency threatening the life of the nation any High Contracting Party may take measures derogating from its obligations under this Convention to the extent strictly required by the exigencies of the situation, provided that such measures are not inconsistent with its other obligations under international law."),
    ("17", "Prohibition of abuse of rights",
     "Nothing in this Convention may be interpreted as implying for any State, group or person any right to engage in any activity or perform any act aimed at the destruction of any of the rights and freedoms set forth herein."),
    ("18", "Limitation on use of restrictions on rights",
     "The restrictions permitted under this Convention to the said rights and freedoms shall not be applied for any purpose other than those for which they have been prescribed."),
    ("34", "Individual applications",
     "The Court may receive applications from any person, non-governmental organisation or group of individuals claiming to be the victim of a violation by one of the High Contracting Parties of the rights set forth in the Convention or the Protocols thereto."),
    ("35", "Admissibility criteria",
     "1. The Court may only deal with the matter after all domestic remedies have been exhausted, according to the generally recognised rules of international law, and within a period of four months from the date on which the final decision was taken."),
    ("41", "Just satisfaction",
     "If the Court finds that there has been a violation of the Convention or the Protocols thereto, and if the internal law of the High Contracting Party concerned allows only partial reparation to be made, the Court shall, if necessary, afford just satisfaction to the injured party."),
    ("46", "Binding force and execution of judgments",
     "1. The High Contracting Parties undertake to abide by the final judgment of the Court in any case to which they are parties.\n2. The final judgment of the Court shall be transmitted to the Committee of Ministers, which shall supervise its execution."),
    ("P1-1", "Protocol No. 1, Article 1 — Protection of property",
     "Every natural or legal person is entitled to the peaceful enjoyment of his possessions. No one shall be deprived of his possessions except in the public interest and subject to the conditions provided for by law and by the general principles of international law."),
    ("P1-2", "Protocol No. 1, Article 2 — Right to education",
     "No person shall be denied the right to education. In the exercise of any functions which it assumes in relation to education and to teaching, the State shall respect the right of parents to ensure such education and teaching in conformity with their own religious and philosophical convictions."),
    ("P1-3", "Protocol No. 1, Article 3 — Right to free elections",
     "The High Contracting Parties undertake to hold free elections at reasonable intervals by secret ballot, under conditions which will ensure the free expression of the opinion of the people in the choice of the legislature."),
    ("P4-2", "Protocol No. 4, Article 2 — Freedom of movement",
     "1. Everyone lawfully within the territory of a State shall, within that territory, have the right to liberty of movement and freedom to choose his residence.\n2. Everyone shall be free to leave any country, including his own."),
    ("P4-4", "Protocol No. 4, Article 4 — Prohibition of collective expulsion of aliens",
     "Collective expulsion of aliens is prohibited."),
    ("P7-2", "Protocol No. 7, Article 2 — Right of appeal in criminal matters",
     "1. Everyone convicted of a criminal offence by a tribunal shall have the right to have his conviction or sentence reviewed by a higher tribunal."),
    ("P7-4", "Protocol No. 7, Article 4 — Right not to be tried or punished twice",
     "1. No one shall be liable to be tried or punished again in criminal proceedings under the jurisdiction of the same State for an offence for which he has already been finally acquitted or convicted in accordance with the law and penal procedure of that State."),
    ("P12-1", "Protocol No. 12, Article 1 — General prohibition of discrimination",
     "1. The enjoyment of any right set forth by law shall be secured without discrimination on any ground such as sex, race, colour, language, religion, political or other opinion, national or social origin, association with a national minority, property, birth or other status."),
)


def echr_convention_enrichment() -> LegislationEnrichment:
    return LegislationEnrichment(
        scheme="coe_treaty",
        identifier="005",
        metadata_source="echr_coe",
        title="Convention for the Protection of Human Rights and Fundamental Freedoms (European Convention on Human Rights)",
        short_title="ECHR / EVRM",
        document_type="treaty",
        date_document="1950-11-04",
        date_entry_into_force="1953-09-03",
        in_force=True,
        subjects=("Human rights", "Fundamental freedoms", "Council of Europe"),
        articles=tuple(
            ArticleProvision(article_label=code, element_type="artikel", title=title, text=text)
            for code, title, text in _ECHR_CORE_ARTICLES
        ),
    )


# ---------------------------------------------------------------------------
# Live HTTP fetchers
# ---------------------------------------------------------------------------

def _http_get(
    url: str, headers: Dict[str, str], *, timeout: int = 30, urlopen: Optional[Callable] = None
) -> bytes:
    opener = urlopen or urllib.request.urlopen
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **headers})
    with opener(req, timeout=timeout) as resp:
        return resp.read()


def fetch_cellar_enrichment(
    celex: str, *, urlopen: Optional[Callable] = None
) -> Optional[LegislationEnrichment]:
    url = CELLAR_RESOURCE_URL.format(celex=urllib.parse.quote(celex.strip(), safe=""))
    meta: Optional[LegislationEnrichment] = None
    for accept in ("application/xml;notice=tree", "application/xml;notice=object"):
        try:
            body = _http_get(url, {"Accept": accept, "Accept-Language": "eng"}, urlopen=urlopen)
            meta = parse_cellar_notice_xml(celex, body)
            break
        except Exception as exc:
            log.debug("CELLAR metadata (%s) failed for %s: %s", accept, celex, exc)

    articles: List[ArticleProvision] = []
    try:
        html_bytes = _http_get(
            url, {"Accept": "application/xhtml+xml", "Accept-Language": "eng"}, urlopen=urlopen
        )
        articles = parse_cellar_xhtml_articles(html_bytes.decode("utf-8", "replace"))
    except Exception as exc:
        log.debug("CELLAR XHTML failed for %s: %s", celex, exc)

    if meta is None and not articles:
        return None
    if meta is None:
        return LegislationEnrichment(
            scheme="celex",
            identifier=celex.upper(),
            metadata_source="cellar_xhtml",
            articles=tuple(articles),
        )
    return LegislationEnrichment(
        scheme=meta.scheme,
        identifier=meta.identifier,
        metadata_source=meta.metadata_source,
        title=meta.title,
        short_title=meta.short_title,
        document_type=meta.document_type,
        date_document=meta.date_document,
        date_entry_into_force=meta.date_entry_into_force,
        in_force=meta.in_force,
        eli=meta.eli,
        subjects=meta.subjects,
        legal_basis=meta.legal_basis,
        amending_acts=meta.amending_acts,
        articles=tuple(articles),
    )


def fetch_bwb_enrichment(
    bwb_id: str, *, today: Optional[dt.date] = None, urlopen: Optional[Callable] = None
) -> Optional[LegislationEnrichment]:
    today_date = today or dt.date.today()
    meta: Optional[BwbSruMetadata] = None
    queries = (
        f"dcterms.identifier=={bwb_id} AND overheidbwb.geldigheidsdatum={today_date.isoformat()}",
        f"dcterms.identifier=={bwb_id}",
    )
    for idx, q in enumerate(queries):
        try:
            url = BWB_SRU_URL.format(query=urllib.parse.quote(q, safe="="))
            body = _http_get(url, {"Accept": "application/xml"}, urlopen=urlopen)
            parsed = parse_bwb_sru_xml(bwb_id, body, today=today_date)
            if parsed is not None:
                if idx == 1:
                    parsed = BwbSruMetadata(
                        bwb_id=parsed.bwb_id,
                        title=parsed.title,
                        subjects=parsed.subjects,
                        start_date=parsed.start_date,
                        end_date=parsed.end_date,
                        in_force=False,
                        toestand_url=parsed.toestand_url,
                    )
                meta = parsed
                break
        except Exception as exc:
            log.debug("BWB SRU failed for %s (%s): %s", bwb_id, q, exc)

    if meta is None:
        return None

    articles: List[ArticleProvision] = []
    if meta.toestand_url:
        try:
            xml_bytes = _http_get(meta.toestand_url, {"Accept": "application/xml"}, urlopen=urlopen)
            articles = parse_bwb_toestand_xml(xml_bytes)
        except Exception as exc:
            log.debug("BWB toestand XML failed for %s: %s", bwb_id, exc)

    return LegislationEnrichment(
        scheme="bwb",
        identifier=meta.bwb_id,
        metadata_source="bwb_sru",
        title=meta.title,
        date_entry_into_force=meta.start_date,
        in_force=meta.in_force,
        subjects=meta.subjects,
        articles=tuple(articles),
    )


# ---------------------------------------------------------------------------
# Artifact I/O & idempotent cle_v2 loader
# ---------------------------------------------------------------------------

def write_enrichment_artifact(path: str, records: Iterable[LegislationEnrichment]) -> int:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".tmp"
    count = 0
    with open(tmp, "w", encoding="utf-8") as handle:
        for rec in records:
            handle.write(json.dumps(rec.to_dict(), ensure_ascii=False, sort_keys=True) + "\n")
            count += 1
    os.replace(tmp, path)
    return count


def read_enrichment_artifact(path: str) -> List[LegislationEnrichment]:
    if not os.path.isfile(path):
        return []
    out: List[LegislationEnrichment] = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            out.append(LegislationEnrichment.from_dict(json.loads(line)))
    return out


_UPDATE_LEGISLATION = f"""
UPDATE {SCHEMA}.legislation
   SET title                 = COALESCE(NULLIF(title, ''), %s),
       short_title           = COALESCE(%s, short_title),
       document_type         = COALESCE(NULLIF(document_type, ''), %s),
       date_document         = COALESCE(%s::date, date_document),
       date_entry_into_force = COALESCE(%s::date, date_entry_into_force),
       in_force              = COALESCE(%s, in_force),
       eli                   = COALESCE(NULLIF(eli, ''), %s),
       subjects              = CASE WHEN %s::text[] IS NOT NULL AND cardinality(%s::text[]) > 0
                                    THEN %s::text[] ELSE subjects END,
       legal_basis           = CASE WHEN %s::text[] IS NOT NULL AND cardinality(%s::text[]) > 0
                                    THEN %s::text[] ELSE legal_basis END,
       amending_acts         = CASE WHEN %s::text[] IS NOT NULL AND cardinality(%s::text[]) > 0
                                    THEN %s::text[] ELSE amending_acts END,
       metadata_source       = %s,
       metadata_fetched_at   = now(),
       fulltext_fetched_at   = CASE WHEN %s THEN now() ELSE fulltext_fetched_at END
 WHERE scheme = %s
   AND identifier = %s
 RETURNING id
"""

_UPDATE_BWB_PROVISION_TEXT = f"""
UPDATE {SCHEMA}.legal_provision
   SET title = COALESCE(NULLIF(title, ''), %s),
       text  = %s
 WHERE legislation_id = %s
   AND (
       (%s::bigint IS NOT NULL AND bwb_label_id = %s::bigint)
       OR (lower(article_label) = lower(%s) AND element_type = %s)
   )
"""

_UPSERT_EXTERNAL_PROVISION = f"""
INSERT INTO {SCHEMA}.legal_provision (
    legislation_id, element_type, article_label, title, text,
    source_dataset, extractor_version
)
VALUES (%s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (legislation_id, element_type, article_label, COALESCE(paragraph, ''))
WHERE source_dataset IS NOT NULL
DO UPDATE SET
    title = COALESCE(NULLIF(EXCLUDED.title, ''), {SCHEMA}.legal_provision.title),
    text  = CASE WHEN EXCLUDED.text IS NOT NULL AND EXCLUDED.text <> ''
                 THEN EXCLUDED.text ELSE {SCHEMA}.legal_provision.text END
"""


def load_enrichment_records(conn, records: Sequence[LegislationEnrichment]) -> Dict[str, int]:
    """Apply LegislationEnrichment records idempotently into cle_v2."""
    stats = {"acts_updated": 0, "acts_missing": 0, "provisions_written": 0}
    if not records:
        return stats
    with conn.cursor() as cur:
        for rec in records:
            subj = list(rec.subjects) or None
            basis = list(rec.legal_basis) or None
            amend = list(rec.amending_acts) or None
            has_articles = bool(rec.articles)
            cur.execute(
                _UPDATE_LEGISLATION,
                (
                    rec.title,
                    rec.short_title,
                    rec.document_type,
                    rec.date_document,
                    rec.date_entry_into_force,
                    rec.in_force,
                    rec.eli,
                    subj, subj, subj,
                    basis, basis, basis,
                    amend, amend, amend,
                    rec.metadata_source,
                    has_articles,
                    rec.scheme,
                    rec.identifier,
                ),
            )
            leg_ids = [row[0] for row in cur.fetchall()]
            if not leg_ids:
                stats["acts_missing"] += 1
                continue
            stats["acts_updated"] += len(leg_ids)
            primary_id = leg_ids[0]
            for art in rec.articles:
                if rec.scheme == "bwb":
                    cur.execute(
                        _UPDATE_BWB_PROVISION_TEXT,
                        (
                            art.title,
                            art.text,
                            primary_id,
                            art.bwb_label_id,
                            art.bwb_label_id,
                            art.article_label,
                            art.element_type,
                        ),
                    )
                    if cur.rowcount == 0:
                        cur.execute(
                            _UPSERT_EXTERNAL_PROVISION,
                            (
                                primary_id,
                                art.element_type,
                                art.article_label,
                                art.title,
                                art.text,
                                rec.metadata_source,
                                EXTRACTOR_VERSION,
                            ),
                        )
                else:
                    cur.execute(
                        _UPSERT_EXTERNAL_PROVISION,
                        (
                            primary_id,
                            art.element_type,
                            art.article_label,
                            art.title,
                            art.text,
                            rec.metadata_source,
                            EXTRACTOR_VERSION,
                        ),
                    )
                stats["provisions_written"] += 1
    conn.commit()
    return stats


def load_enrichment_artifact(conn, path: str) -> Dict[str, int]:
    """Load a legislation_enrichment.jsonl artifact (used by etl-promoter replay)."""
    return load_enrichment_records(conn, read_enrichment_artifact(path))


def select_pending_acts(conn, scheme: str, limit: int) -> List[str]:
    """Select the highest-cited acts of `scheme` whose fulltext has not yet been fetched."""
    if limit <= 0:
        return []
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT l.identifier
              FROM {SCHEMA}.legislation l
              LEFT JOIN LATERAL (
                  SELECT count(*) AS cnt
                    FROM {SCHEMA}.case_law_reference r
                   WHERE r.legislation_id = l.id
                   LIMIT 5000
              ) ref ON true
             WHERE l.scheme = %s
               AND l.identifier IS NOT NULL
               AND l.fulltext_fetched_at IS NULL
             ORDER BY COALESCE(ref.cnt, 0) DESC, l.id ASC
             LIMIT %s
            """,
            (scheme, limit),
        )
        rows = [row[0] for row in cur.fetchall()]
    conn.rollback()
    return rows


def enrich_connection(
    conn,
    *,
    limit_celex: int = 30,
    limit_bwb: int = 30,
    include_echr: bool = True,
    pause: float = 0.25,
    out_path: Optional[str] = None,
    load: bool = True,
    urlopen: Optional[Callable] = None,
) -> Dict[str, Any]:
    """Weekly incremental enrichment task for enrichment_sync_etl."""
    records: List[LegislationEnrichment] = []
    errors = 0

    if include_echr:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT 1 FROM {SCHEMA}.legislation WHERE scheme = 'coe_treaty' AND identifier = '005' "
                "AND fulltext_fetched_at IS NULL LIMIT 1"
            )
            needs_echr = cur.fetchone() is not None
        conn.rollback()
        if needs_echr:
            records.append(echr_convention_enrichment())

    for celex in select_pending_acts(conn, "celex", limit_celex):
        rec = fetch_cellar_enrichment(celex, urlopen=urlopen)
        if rec is not None:
            records.append(rec)
        else:
            errors += 1
        if pause:
            time.sleep(pause)

    for bwb_id in select_pending_acts(conn, "bwb", limit_bwb):
        rec = fetch_bwb_enrichment(bwb_id, urlopen=urlopen)
        if rec is not None:
            records.append(rec)
        else:
            errors += 1
        if pause:
            time.sleep(pause)

    if out_path:
        write_enrichment_artifact(out_path, records)

    load_stats = load_enrichment_records(conn, records) if load and records else {}
    return {
        "fetched_acts": len(records),
        "fetched_articles": sum(len(r.articles) for r in records),
        "errors": errors,
        "load": load_stats,
    }


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Enrich legislation metadata and structured article texts")
    parser.add_argument("--limit-celex", type=int, default=30)
    parser.add_argument("--limit-bwb", type=int, default=30)
    parser.add_argument("--out", default=None)
    parser.add_argument("--no-load", action="store_true")
    args = parser.parse_args(argv)

    from data_loading.clients.postgres import PostgresCLEClient

    with PostgresCLEClient() as client:
        summary = enrich_connection(
            client._get_conn(),
            limit_celex=args.limit_celex,
            limit_bwb=args.limit_bwb,
            out_path=args.out,
            load=not args.no_load,
        )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
