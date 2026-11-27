"""Declarative multilingual international treaty matcher backed by treaties_catalog.json.

Uses a pure-Python Aho-Corasick automaton (O(len(text)), zero external dependencies)
over all multilingual phrases and uppercase acronyms in `treaties_catalog.json` so
scanning a 50 KB judgment against 200-400+ treaties runs in ~1-2 ms.

Each raw hit is verified with:
  1. Strict non-alphanumeric word boundaries (and ECLI colon exclusion for acronyms).
  2. Exact uppercase check for acronyms (e.g. CMR, TRIPS, CISG, VCLT, EPC, PCT).
  3. Optional ±300-char `require_context` and `exclude_context` disambiguation guards
     (e.g. 1951 Refugee vs 1949 IHL Geneva Conventions, 1961 vs 1996 European Social
     Charter, 1980 vs 1996 Hague Conventions, Berne copyright vs Bern wildlife).
  4. Preceding multilingual article/paragraph extraction (`Article 31(1) of the ...`,
     `art. 3, § 2, de la ...`, `Artikel 12 lid 1 van het ...`), bounded by `max_article`.
"""

from __future__ import annotations

import json
import os
import re
from collections import deque
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict, FrozenSet, Iterable, List, Optional, Sequence, Set, Tuple

CATALOG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "legislation",
    "treaties_catalog.json",
)


@dataclass(frozen=True)
class TreatyEntry:
    scheme: str
    identifier: str
    jurisdiction: str
    document_type: str
    title: str
    enacted_year: int
    max_article: int
    category: str
    phrases: Tuple[str, ...]
    acronyms: Tuple[str, ...] = ()
    require_context: Tuple[str, ...] = ()
    exclude_context: Tuple[str, ...] = ()
    bwbv_ids: Tuple[str, ...] = ()
    celex_ids: Tuple[str, ...] = ()
    enacted_date: Optional[str] = None
    skip_in_echr: bool = False

    @property
    def key(self) -> Tuple[str, str]:
        return (self.scheme, self.identifier)


@dataclass(frozen=True)
class CatalogHit:
    scheme: str
    identifier: str
    article: Optional[str]
    raw_subdivision: Optional[str]
    match_method: str  # 'treaty_article' | 'treaty_name'
    confidence: float
    start: int
    end: int
    raw_text: str


@lru_cache(maxsize=4)
def load_catalog(path: str = CATALOG_PATH) -> Tuple[TreatyEntry, ...]:
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    entries: List[TreatyEntry] = []
    for raw in data["treaties"]:
        entries.append(
            TreatyEntry(
                scheme=raw["scheme"],
                identifier=raw["identifier"],
                jurisdiction=raw["jurisdiction"],
                document_type=raw.get("document_type", "convention"),
                title=raw["title"],
                enacted_year=int(raw["enacted_year"]),
                max_article=int(raw.get("max_article", 200)),
                category=raw.get("category", "other"),
                phrases=tuple(raw.get("phrases") or ()),
                acronyms=tuple(raw.get("acronyms") or ()),
                require_context=tuple(w.lower() for w in (raw.get("require_context") or ())),
                exclude_context=tuple(w.lower() for w in (raw.get("exclude_context") or ())),
                bwbv_ids=tuple(raw.get("bwbv_ids") or ()),
                celex_ids=tuple(raw.get("celex_ids") or ()),
                enacted_date=raw.get("enacted_date"),
                skip_in_echr=bool(raw.get("skip_in_echr", False)),
            )
        )
    return tuple(entries)


class _AhoCorasick:
    """Compact pure-Python Aho-Corasick multi-pattern matcher over lowercased strings."""

    def __init__(self, patterns: Iterable[Tuple[str, Tuple[int, bool, str]]]) -> None:
        self._next: List[Dict[str, int]] = [{}]
        self._fail: List[int] = [0]
        self._out: List[List[Tuple[int, int, bool, str]]] = [[]]  # (pat_len, treaty_idx, is_acronym, orig)

        for pat_lower, (treaty_idx, is_acronym, orig) in patterns:
            if not pat_lower:
                continue
            state = 0
            for ch in pat_lower:
                nxt = self._next[state].get(ch)
                if nxt is None:
                    nxt = len(self._next)
                    self._next[state][ch] = nxt
                    self._next.append({})
                    self._fail.append(0)
                    self._out.append([])
                state = nxt
            self._out[state].append((len(pat_lower), treaty_idx, is_acronym, orig))

        queue: deque[int] = deque()
        for ch, nxt in self._next[0].items():
            self._fail[nxt] = 0
            queue.append(nxt)
        while queue:
            curr = queue.popleft()
            for ch, nxt in self._next[curr].items():
                queue.append(nxt)
                f = self._fail[curr]
                while f and ch not in self._next[f]:
                    f = self._fail[f]
                self._fail[nxt] = self._next[f].get(ch, 0)
                if self._out[self._fail[nxt]]:
                    self._out[nxt].extend(self._out[self._fail[nxt]])

    def finditer(self, text_lower: str) -> Iterable[Tuple[int, int, int, bool, str]]:
        state = 0
        nxt_list = self._next
        fail_list = self._fail
        out_list = self._out
        for i, ch in enumerate(text_lower):
            while state and ch not in nxt_list[state]:
                state = fail_list[state]
            state = nxt_list[state].get(ch, 0)
            outs = out_list[state]
            if outs:
                end = i + 1
                for pat_len, treaty_idx, is_acronym, orig in outs:
                    yield end - pat_len, end, treaty_idx, is_acronym, orig


@lru_cache(maxsize=4)
def _compiled_automaton(path: str = CATALOG_PATH) -> Tuple[Tuple[TreatyEntry, ...], _AhoCorasick]:
    entries = load_catalog(path)
    patterns: List[Tuple[str, Tuple[int, bool, str]]] = []
    seen: Set[Tuple[str, int, bool]] = set()
    for idx, entry in enumerate(entries):
        for phrase in entry.phrases:
            pl = _normalize_1to1(phrase)
            if len(pl) < 5:
                continue
            key = (pl, idx, False)
            if key not in seen:
                seen.add(key)
                patterns.append((pl, (idx, False, phrase)))
        for acro in entry.acronyms:
            al = _normalize_1to1(acro)
            if len(al) < 3:
                continue
            key = (al, idx, True)
            if key not in seen:
                seen.add(key)
                patterns.append((al, (idx, True, acro)))
    return entries, _AhoCorasick(patterns)


# Preceding article + subdivision right before a matched treaty name (EN/FR/DE/NL/ES/IT).
_PRECEDING_ART_RE = re.compile(
    r"(?:\b(?:Articles?|Art\.|Artikel|art[íi]culos?|articoli?)\s+"
    r"(\d{1,3}(?:\s*(?:bis|ter|quater))?)"
    r"(?:\s*(?:\((\d{1,2})\)|(?:,\s*)?(?:paragraph|para\.?|§|paragraphe|Abs\.|Absatz|lid|apartado|comma)\s*(\d{1,2})))?"
    r"(?:\s*(?:\(([a-z])\)|(?:,\s*)?(?:point|letter|lit\.|onder)\s*\(?([a-z])\)?))?"
    r")\s*(?:,|;)?\s*"
    r"(?:of(?:\s+the)?|under(?:\s+the)?|in(?:\s+the)?|"
    r"de(?:\s+la|\s+l['’])?|du|des|d['’]|"
    r"der|des|dem|"
    r"van(?:\s+het|\s+de)?|"
    r"del|de\s+los|della|dello|dell['’])?\s*"
    r"(?:(?:19|20)\d{2}\s+)?(?:UN\s+|United\s+Nations\s+|Council\s+of\s+Europe\s+)?$",
    re.IGNORECASE,
)


def _is_word_boundary(text: str, start: int, end: int, is_acronym: bool) -> bool:
    if start > 0:
        prev = text[start - 1]
        if prev.isalnum() or prev == "_":
            return False
        if is_acronym and prev in (":", "/", "-"):
            return False
    if end < len(text):
        nxt = text[end]
        if nxt.isalnum() or nxt == "_":
            return False
        if is_acronym and nxt in (":", "/"):
            return False
    return True


def _article_number_int(art_raw: str) -> Optional[int]:
    m = re.match(r"(\d{1,3})", art_raw.strip())
    return int(m.group(1)) if m else None


def _format_subdivision(art_raw: str, p1: Optional[str], p2: Optional[str], l1: Optional[str], l2: Optional[str]) -> Tuple[str, str]:
    art = re.sub(r"\s+", "", art_raw.strip())
    para = p1 or p2
    letter = l1 or l2
    sub = art
    if para:
        sub = f"{sub}({para})"
    if letter:
        sub = f"{sub}({letter})"
    return art, sub


def _overlaps(span: Tuple[int, int], covered: Sequence[Tuple[int, int]]) -> bool:
    s, e = span
    return any(s < ce and e > cs for cs, ce in covered)


_NORM_TRANS = str.maketrans({
    "\u0130": "i",  # Turkish 'İ'.lower() expands to 2 codepoints ('i\u0307'); keep 1:1 length
    "\u2018": "'",
    "\u2019": "'",
    "\u02bc": "'",
    "\u00a0": " ",
    "\u202f": " ",
    "\n": " ",
    "\r": " ",
    "\t": " ",
    "\u2011": "-",
    "\u2013": "-",
    "\u2014": "-",
})


def _normalize_1to1(text: str) -> str:
    """Strict 1-to-1 character normalization (guarantees len(out) == len(text))."""
    translated = text.translate(_NORM_TRANS)
    out = translated.lower()
    if len(out) != len(text):
        out = "".join(c.lower()[0] for c in translated)
    return out


def scan(
    text: str,
    *,
    skip_keys: FrozenSet[Tuple[str, str]] = frozenset(),
    skip_echr_core: bool = False,
    path: str = CATALOG_PATH,
) -> List[CatalogHit]:
    """Scan one case text against the declarative multilingual treaty catalog."""
    if not text:
        return []
    entries, automaton = _compiled_automaton(path)
    text_lower = _normalize_1to1(text)

    # Collect valid candidate spans first, sorted longest-match-first so specific
    # titles (e.g. Revised European Social Charter, Optional Protocol to CAT) take
    # precedence over shorter overlapping titles.
    raw_matches: List[Tuple[int, int, int, int, bool]] = []  # (-len, start, end, idx, is_acronym)
    for start, end, idx, is_acronym, orig in automaton.finditer(text_lower):
        entry = entries[idx]
        if skip_echr_core and entry.skip_in_echr:
            continue
        if entry.key in skip_keys:
            continue
        if not _is_word_boundary(text, start, end, is_acronym):
            continue
        if is_acronym and text[start:end] != orig:
            continue
        if entry.exclude_context:
            ex_ctx = text_lower[max(0, start - 300) : min(len(text_lower), end + 300)]
            if any(ex in ex_ctx for ex in entry.exclude_context):
                continue
        if entry.require_context:
            req_ctx = text_lower[max(0, start - 600) : min(len(text_lower), end + 600)]
            if not any(req in req_ctx for req in entry.require_context):
                continue
        raw_matches.append((-(end - start), start, end, idx, is_acronym))

    if not raw_matches:
        return []

    raw_matches.sort()
    covered: List[Tuple[int, int]] = []
    article_hits: List[CatalogHit] = []
    whole_hits: Dict[Tuple[str, str], CatalogHit] = {}
    acts_with_articles: Set[Tuple[str, str]] = set()

    for _neg_len, start, end, idx, is_acronym in raw_matches:
        if _overlaps((start, end), covered):
            continue
        entry = entries[idx]
        prefix = text[max(0, start - 95) : start]
        art_m = _PRECEDING_ART_RE.search(prefix)
        if art_m is not None:
            art_raw, p1, p2, l1, l2 = art_m.groups()
            num = _article_number_int(art_raw)
            if num is not None and 1 <= num <= entry.max_article:
                art, sub = _format_subdivision(art_raw, p1, p2, l1, l2)
                full_start = max(0, start - 95) + art_m.start()
                raw_ref = " ".join(text[full_start:end].split())[:200]
                article_hits.append(
                    CatalogHit(
                        scheme=entry.scheme,
                        identifier=entry.identifier,
                        article=art,
                        raw_subdivision=sub,
                        match_method="treaty_article",
                        confidence=0.94 if not is_acronym else 0.90,
                        start=full_start,
                        end=end,
                        raw_text=raw_ref,
                    )
                )
                covered.append((full_start, end))
                acts_with_articles.add(entry.key)
                continue

        covered.append((start, end))
        if entry.key not in whole_hits:
            raw_ref = " ".join(text[start:end].split())[:200]
            whole_hits[entry.key] = CatalogHit(
                scheme=entry.scheme,
                identifier=entry.identifier,
                article=None,
                raw_subdivision=None,
                match_method="treaty_name",
                confidence=0.90 if not is_acronym else 0.86,
                start=start,
                end=end,
                raw_text=raw_ref,
            )

    out = list(article_hits)
    for key, hit in whole_hits.items():
        if key not in acts_with_articles:
            out.append(hit)
    return out


# Selective Postgres to_tsquery('simple', ...) candidate groups covering all major
# catalog categories without triggering GIN statement timeouts.
def candidate_tsquery_groups(skip_echr_core: bool = False) -> Tuple[str, ...]:
    """Return compact PostgreSQL simple-dictionary tsquery strings covering the catalog."""
    groups = [
        # 1. Human rights, refugee, statelessness, UN core
        "'ICCPR' | 'ICESCR' | 'ICERD' | 'CEDAW' | 'UNCAT' | 'UNCRC' | 'UNCRPD' | 'CRPD' | 'OPCAT' | 'FCNM' | "
        "('Status' & 'Refugees') | ('statut' & 'réfugiés') | ('statut' & 'apatrides') | ('Stateless' & 'Persons') | "
        "('Covenant' & 'Civil' & 'Political') | ('Pacte' & 'civils' & 'politiques') | "
        "('Covenant' & 'Economic' & 'Cultural') | ('Pacte' & 'économiques' & 'culturels') | "
        "('Convention' & 'against' & 'Torture') | ('Convention' & 'contre' & 'torture') | "
        "('Rights' & 'Child' & 'Convention') | ('droits' & 'enfant' & 'Convention') | "
        "('Persons' & 'Disabilities') | ('personnes' & 'handicapées') | "
        "('Prevention' & 'Torture' & 'European') | ('prévention' & 'torture' & 'européenne') | "
        "('Genocide' & 'Convention') | ('crime' & 'génocide')",
        # 2. CoE social, criminal, data protection, Istanbul, Lanzarote, Budapest, Oviedo
        "('Social' & 'Charter') | ('Charte' & 'sociale') | ('Sozialcharta') | ('Sociaal' & 'Handvest') | "
        "('Extradition' & 'European') | ('extradition' & 'européenne') | "
        "('Mutual' & 'Assistance' & 'Criminal') | ('entraide' & 'judiciaire' & 'pénale') | "
        "('Transfer' & 'Sentenced' & 'Persons') | ('transfèrement' & 'personnes' & 'condamnées') | "
        "('Convention' & '108') | ('Automatic' & 'Processing' & 'Personal' & 'Data') | "
        "('Istanbul' & 'Convention') | ('Lanzarote' & 'Convention') | ('Oviedo' & 'Convention') | "
        "('Cybercrime') | ('cybercriminalité') | ('National' & 'Minorities') | ('minorités' & 'nationales') | "
        "('Trafficking' & 'Human' & 'Beings') | ('traite' & 'êtres' & 'humains') | "
        "('European' & 'Convention' & 'Nationality') | ('Local' & 'Self-Government')",
        # 3. Public international law, VCLT, diplomatic, ICC, IHL, UNCLOS, arbitration
        "'VCLT' | 'VCDR' | 'VCCR' | 'UNCLOS' | 'UNTOC' | 'UNCAC' | 'ICSID' | 'CIRDI' | "
        "('Law' & 'Treaties' & 'Vienna') | ('droit' & 'traités' & 'Vienne') | ('Wiener' & 'Vertragsrechtskonvention') | "
        "('Diplomatic' & 'Relations' & 'Vienna') | ('Consular' & 'Relations' & 'Vienna') | "
        "('Rome' & 'Statute') | ('Statut' & 'Rome') | ('Palermo' & 'Convention') | "
        "('Charter' & 'United' & 'Nations') | ('Charte' & 'Nations' & 'Unies') | "
        "('Foreign' & 'Arbitral' & 'Awards') | ('sentences' & 'arbitrales' & 'étrangères') | "
        "('Law' & 'Sea' & 'United' & 'Nations') | ('droit' & 'mer' & 'Montego') | "
        "('Geneva' & 'Convention' & 'Civilian') | ('Geneva' & 'Convention' & 'Prisoners') | ('Hague' & 'Regulations' & '1907')",
        # 4. Private international law (HCCH, Brussels, Rome, Lugano, CISG) & ILO
        "'CISG' | ('Hague' & 'Abduction') | ('enlèvement' & 'international' & 'enfants') | "
        "('Hague' & 'Convention' & '1980') | ('Hague' & 'Convention' & '1996') | ('Hague' & 'Service' & 'Convention') | "
        "('Hague' & 'Evidence' & 'Convention') | ('Apostille' & 'Convention') | ('Choice' & 'Court' & 'Agreements') | "
        "('Parental' & 'Responsibility' & '1996') | ('Intercountry' & 'Adoption') | "
        "('Lugano' & 'Convention') | ('Convention' & 'Lugano') | ('Brussels' & 'Convention' & '1968') | "
        "('Rome' & 'Convention' & 'Contractual') | ('Schengen' & 'Implementing') | 'CISA' | "
        "('ILO' & 'Convention') | ('OIT' & 'Convention') | ('Forced' & 'Labour' & 'Convention')",
        # 5. Trade, IP, Transport, Environment, Energy, Regional
        "'TRIPS' | 'ADPIC' | 'GATT' | 'GATS' | 'CITES' | 'MARPOL' | 'SOLAS' | 'COTIF' | 'CMNI' | 'CLNI' | "
        "'OSPAR' | 'WPPT' | 'UPOV' | 'UPCA' | 'BCIP' | 'EUCARIS' | "
        "('Aarhus' & 'Convention') | ('Convention' & 'Aarhus') | ('Basel' & 'Convention' & 'Wastes') | "
        "('Espoo' & 'Convention') | ('Ramsar' & 'Convention') | ('Kyoto' & 'Protocol') | ('Paris' & 'Agreement' & 'Climate') | "
        "('Biological' & 'Diversity') | ('Energy' & 'Charter' & 'Treaty') | ('Charte' & 'énergie') | "
        "('Berne' & 'Convention') | ('Convention' & 'Berne') | ('Paris' & 'Convention' & 'Industrial' & 'Property') | "
        "('European' & 'Patent' & 'Convention') | ('brevet' & 'européen') | ('Patent' & 'Cooperation' & 'Treaty') | "
        "('WIPO' & 'Copyright') | ('Madrid' & 'Protocol') | ('Chicago' & 'Convention') | "
        "('Montreal' & 'Convention' & 'Air') | ('Warsaw' & 'Convention' & 'Air') | ('Carriage' & 'Goods' & 'Road') | "
        "('EEA' & 'Agreement') | ('Ankara' & 'Agreement') | ('Free' & 'Movement' & 'Swiss') | ('World' & 'Heritage' & 'Convention')",
    ]
    if not skip_echr_core:
        groups.insert(
            0,
            "'ECHR' | 'CEDH' | 'EMRK' | 'EVRM' | 'CEDU' | "
            "('European' & 'Convention' & 'Human' & 'Rights') | "
            "('Convention' & 'européenne' & 'droits' & 'homme') | "
            "('Europäische' & 'Menschenrechtskonvention')",
        )
    return tuple(groups)
