"""Cross-court judicial panel & Advocate General extraction (Track B).

Extracts normalized judge and Advocate General records into `cle_v2.judge` and
`cle_v2.case_judge` from:
  1. Dutch Rechtspraak judgment closing blocks (`rs_text_judge`):
       "Aldus gewezen door mrs. A.B. Jansen, voorzitter, C.D. de Vries en
        E.F. Bakker, raadsheren, in tegenwoordigheid van ..."
  2. Dutch Parket bij de Hoge Raad conclusions (`rs_phr_ag`, `ECLI:NL:PHR:*`):
       "De Procureur-Generaal bij de Hoge Raad der Nederlanden,
        mr. F.F. Langemeijer, Advocaat-Generaal"
  3. ECtHR HUDOC panel headers (`echr_hudoc_judge`, EN & FR):
       "composed of: Robert Spano, President, Marko Bošnjak, ..., Judges,
        and Hasan Bakırcı, Section Registrar"

Clerks (`griffier`) and registrars (`Registrar` / `Greffier`) are explicitly
excluded. Writes idempotent JSONL artifacts (`cross_court_judges.jsonl`) that
`etl-promoter` replays into production via `load_artifact(conn, path)`.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

log = logging.getLogger(__name__)

SCHEMA = "cle_v2"
EXTRACTOR_VERSION = "cross_court_judges/1.0.0"


@dataclass(frozen=True)
class JudgeRecord:
    source_ecli: str
    name: str
    role: str  # 'judge' | 'advocate_general'
    source_dataset: str  # 'rs_text_judge' | 'rs_phr_ag' | 'echr_hudoc_judge'
    extractor_version: str = EXTRACTOR_VERSION
    confidence: float = 0.90

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "JudgeRecord":
        return cls(
            source_ecli=str(data["source_ecli"]),
            name=str(data["name"]),
            role=str(data["role"]),
            source_dataset=str(data["source_dataset"]),
            extractor_version=str(data.get("extractor_version") or EXTRACTOR_VERSION),
            confidence=float(data.get("confidence", 0.90)),
        )


# ---------------------------------------------------------------------------
# Dutch Rechtspraak judges & Parket bij de Hoge Raad AGs
# ---------------------------------------------------------------------------

_RS_PANEL_BLOCK_RE = re.compile(
    r"(?:Aldus\s+(?:gewezen|vastgesteld|gedaan|beslist)"
    r"|Dit\s+(?:arrest|vonnis)\s+is\s+(?:gewezen|gedaan)"
    r"|Deze\s+(?:uitspraak|beschikking)\s+is\s+(?:gedaan|gegeven|gewezen))"
    r"\s+door\s+(.*?)(?=\s*(?:,\s*)?(?:in\s+(?:tegenwoordigheid|bijwezen|aanwezigheid)\s+van"
    r"|bijgestaan\s+door"
    r"|en\s+(?:in\s+het\s+openbaar\s+)?uitgesproken"
    r"|in\s+het\s+openbaar\s+uitgesproken"
    r"|griffier\b"
    r"|\.\s*(?:\n|$)|$))",
    re.IGNORECASE | re.DOTALL,
)

_NL_HONORIFIC_RE = re.compile(
    r"^(?:(?:prof|dr|mr|mrs|ir|ing|mw|mevr|dhr)\.\s*|mevrouw\s+|de\s+heer\s+|mr\s+|mrs\s+)+",
    re.IGNORECASE,
)

_NL_ROLE_STOPWORDS: Set[str] = {
    "voorzitter",
    "vice-president",
    "president",
    "raadsheer",
    "raadsheren",
    "rechter",
    "rechters",
    "kantonrechter",
    "voorzieningenrechter",
    "kinderrechter",
    "politierechter",
    "staatsraad",
    "staatsraden",
    "lid",
    "leden",
    "lid-voorzitter",
    "plaatsvervangend",
    "raadsheer-plaatsvervanger",
    "rechter-plaatsvervanger",
    "staatsraad in buitengewone dienst",
    "enkelvoudige kamer",
    "meervoudige kamer",
    "als voorzitter",
    "als rechters",
    "als raadsheren",
    "als leden",
    "als lid",
    "griffier",
    "waarnemend griffier",
    "advocaat-generaal",
    "procureur-generaal",
}

_NL_TRAILING_ROLE_RE = re.compile(
    r"\s*(?:\([^)]*\))?\s*(?:als\s+)?(?:voorzitter|vice-president|president|raadsher(?:en)?|"
    r"raadsheer(?:-plaatsvervanger)?|rechters?|rechter-plaatsvervanger|kantonrechter|"
    r"voorzieningenrechter|kinderrechter|politierechter|staatsrad(?:en)?|staatsraad|"
    r"leden|lid|advocaat-generaal|procureur-generaal|a-g)\.?$",
    re.IGNORECASE,
)

_PHR_AG_SIGNATURE_RE = re.compile(
    r"(?:De\s+(?:waarnemend\s+|plv\.?\s+)?(?:Procureur|Advocaat)-Generaal\s+bij\s+de\s+Hoge\s+Raad"
    r"[^\n]{0,80}\n+\s*(?:w\.g\.?\s*)?([^\n]{4,100})"
    r"|(?:prof\.?\s*)?(?:dr\.?\s*)?mr\.?\s+([A-ZÀ-Ý][A-Za-zÀ-ÿ.'\- ]{2,70}?)\s*,?\s*\n?\s*(?:plv\.?\s*)?(?:Advocaat-Generaal|A-G)\b)",
    re.IGNORECASE,
)

_VALID_NAME_RE = re.compile(r"^[^\W\d_](?:[^\W\d_]|[.'’\- ]){2,75}$", re.UNICODE)


def _clean_dutch_name(raw: str) -> Optional[str]:
    text = re.sub(r"\s+", " ", (raw or "").strip(" ,;:.()\n\t"))
    if not text:
        return None
    text = _NL_HONORIFIC_RE.sub("", text).strip(" ,;:.")
    text = _NL_TRAILING_ROLE_RE.sub("", text).strip(" ,;:.")
    text = _NL_HONORIFIC_RE.sub("", text).strip(" ,;:.")
    if not text or text.lower() in _NL_ROLE_STOPWORDS:
        return None
    if any(ch.isdigit() for ch in text):
        return None
    if not text[0].isupper() or not _VALID_NAME_RE.match(text):
        return None
    # Require either initials + surname ("A.B. Jansen") or >= 2 words
    if " " not in text and "." not in text:
        return None
    if len(text) < 4 or len(text) > 70:
        return None
    return text


def extract_rs_judges(fulltext: str, ecli: str) -> List[JudgeRecord]:
    """Extract Dutch judges (or Hoge Raad AG for ECLI:NL:PHR:*) from fulltext."""
    if not fulltext or not ecli:
        return []
    out: List[JudgeRecord] = []
    seen: Set[Tuple[str, str]] = set()
    tail = fulltext[-3000:] if len(fulltext) > 3000 else fulltext

    # 1. Parket bij de Hoge Raad conclusions -> Advocate General
    if ecli.upper().startswith("ECLI:NL:PHR:"):
        for m in _PHR_AG_SIGNATURE_RE.finditer(tail):
            raw = m.group(1) or m.group(2)
            name = _clean_dutch_name(raw or "")
            if name and (name.lower(), "advocate_general") not in seen:
                seen.add((name.lower(), "advocate_general"))
                out.append(
                    JudgeRecord(
                        source_ecli=ecli,
                        name=name,
                        role="advocate_general",
                        source_dataset="rs_phr_ag",
                        confidence=0.92,
                    )
                )
        return out

    # 2. Regular Rechtspraak judgments -> panel judges
    for m in _RS_PANEL_BLOCK_RE.finditer(tail):
        block = m.group(1)
        # Split on commas, semicolons, and Dutch conjunction ' en '
        tokens = re.split(r"\s*[,;]\s*|\s+en\s+", block)
        for tok in tokens:
            name = _clean_dutch_name(tok)
            if name and (name.lower(), "judge") not in seen:
                seen.add((name.lower(), "judge"))
                out.append(
                    JudgeRecord(
                        source_ecli=ecli,
                        name=name,
                        role="judge",
                        source_dataset="rs_text_judge",
                        confidence=0.90,
                    )
                )
    return out


# ---------------------------------------------------------------------------
# ECtHR HUDOC judicial panel extraction (EN + FR)
# ---------------------------------------------------------------------------

_ECHR_COMPOSED_EN_RE = re.compile(
    r"composed\s+of\s*:?\s*(.{10,1600}?)\s*,?\s*(?:Judges?|and\s+(?:the\s+)?[A-ZÀ-Ý][^,\n]{2,60},\s*(?:Deputy\s+)?(?:Section\s+|Grand\s+Chamber\s+)?Registrar)",
    re.IGNORECASE | re.DOTALL,
)
_ECHR_COMPOSED_FR_RE = re.compile(
    r"compos[eé]e\s+de\s*:?\s*(.{10,1600}?)\s*,?\s*(?:juges?|et\s+de\s+[A-ZÀ-Ý][^,\n]{2,60},\s*(?:greffier|greffi[eè]re))",
    re.IGNORECASE | re.DOTALL,
)

_ECHR_ROLE_WORDS: Set[str] = {
    "president",
    "vice-president",
    "section president",
    "acting president",
    "judge",
    "judges",
    "ad hoc judge",
    "judge ad hoc",
    "président",
    "présidente",
    "vice-président",
    "vice-présidente",
    "juge",
    "juges",
    "juge ad hoc",
    "registrar",
    "section registrar",
    "deputy registrar",
    "deputy section registrar",
    "greffier",
    "greffière",
    "greffier de section",
    "greffier adjoint",
}

_ECHR_STRIP_ROLE_RE = re.compile(
    r"\s*(?:\([^)]*\))?\s*,?\s*(?:acting\s+|section\s+)?(?:vice-)?(?:president|pr[eé]sidente?|judges?|juges?|ad\s+hoc\s+judge|juge\s+ad\s+hoc)\.?$",
    re.IGNORECASE,
)


def _clean_echr_name(raw: str) -> Optional[str]:
    text = re.sub(r"\s+", " ", (raw or "").strip(" ,;:.()\n\t"))
    text = re.sub(r"^(?:Mr|Ms|Mrs|Mme|M\.|MM\.|Sir|Lord|Lady|Judge)\s+", "", text, flags=re.IGNORECASE)
    text = _ECHR_STRIP_ROLE_RE.sub("", text).strip(" ,;:.")
    if not text or text.lower() in _ECHR_ROLE_WORDS:
        return None
    if "registrar" in text.lower() or "greffier" in text.lower() or "greffière" in text.lower():
        return None
    if any(ch.isdigit() for ch in text):
        return None
    if " " not in text:
        return None
    if not text[0].isupper() or not _VALID_NAME_RE.match(text):
        return None
    if len(text) < 5 or len(text) > 70:
        return None
    return text


def extract_echr_judges(fulltext: str, ecli: str) -> List[JudgeRecord]:
    """Extract ECtHR Chamber / Grand Chamber judges from HUDOC fulltext header."""
    if not fulltext or not ecli:
        return []
    head = fulltext[:4000]
    match = _ECHR_COMPOSED_EN_RE.search(head) or _ECHR_COMPOSED_FR_RE.search(head)
    if not match:
        return []

    block = match.group(1)
    # Trim any trailing ", and <Registrar Name>" fragment before parsing judges
    block = re.sub(r",?\s*\b(?:and|et\s+de)\s+[A-ZÀ-Ý][^,\n]{2,60},\s*(?:Deputy\s+)?(?:Section\s+)?(?:Registrar|greffier).*$", "", block, flags=re.IGNORECASE | re.DOTALL)

    out: List[JudgeRecord] = []
    seen: Set[str] = set()
    for part in re.split(r"[\n,;]+|\s+\band\b\s+|\s+\bet\b\s+", block):
        name = _clean_echr_name(part)
        if name and name.lower() not in seen:
            seen.add(name.lower())
            out.append(
                JudgeRecord(
                    source_ecli=ecli,
                    name=name,
                    role="judge",
                    source_dataset="echr_hudoc_judge",
                    confidence=0.90,
                )
            )
    return out


# ---------------------------------------------------------------------------
# Artifact I/O & idempotent cle_v2 loader
# ---------------------------------------------------------------------------

def write_artifact(path: str, records: Iterable[JudgeRecord]) -> int:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".tmp"
    count = 0
    with open(tmp, "w", encoding="utf-8") as handle:
        for rec in records:
            handle.write(json.dumps(rec.to_dict(), ensure_ascii=False, sort_keys=True) + "\n")
            count += 1
    os.replace(tmp, path)
    return count


def read_artifact(path: str) -> List[JudgeRecord]:
    if not os.path.isfile(path):
        return []
    out: List[JudgeRecord] = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            out.append(JudgeRecord.from_dict(json.loads(line)))
    return out


_INSERT_JUDGES = f"""
INSERT INTO {SCHEMA}.judge (full_name)
SELECT DISTINCT v FROM unnest(%s::text[]) AS v
 WHERE NOT EXISTS (SELECT 1 FROM {SCHEMA}.judge j WHERE lower(j.full_name) = lower(v))
"""

_INSERT_CASE_JUDGES = f"""
INSERT INTO {SCHEMA}.case_judge (case_id, judge_id, role, source_dataset, extractor_version, confidence)
SELECT c.id, j.id, u.role, u.source_dataset, u.extractor_version, u.confidence
  FROM unnest(%s::text[], %s::text[], %s::text[], %s::text[], %s::text[], %s::real[])
       AS u(ecli, name, role, source_dataset, extractor_version, confidence)
  JOIN {SCHEMA}.cases c ON c.ecli = u.ecli
  JOIN LATERAL (
      SELECT id FROM {SCHEMA}.judge j2
       WHERE lower(j2.full_name) = lower(u.name)
       ORDER BY id LIMIT 1
  ) j ON true
ON CONFLICT (case_id, judge_id, role) DO NOTHING
"""


def load_records(conn, records: Sequence[JudgeRecord], batch_size: int = 2000) -> Dict[str, int]:
    """Load JudgeRecord rows idempotently into cle_v2.judge and cle_v2.case_judge."""
    stats = {"records": len(records), "inserted": 0}
    if not records:
        return stats
    with conn.cursor() as cur:
        for i in range(0, len(records), batch_size):
            batch = records[i : i + batch_size]
            names = sorted({r.name for r in batch})
            cur.execute(_INSERT_JUDGES, (names,))
            cur.execute(
                _INSERT_CASE_JUDGES,
                (
                    [r.source_ecli for r in batch],
                    [r.name for r in batch],
                    [r.role for r in batch],
                    [r.source_dataset for r in batch],
                    [r.extractor_version for r in batch],
                    [r.confidence for r in batch],
                ),
            )
            stats["inserted"] += max(cur.rowcount, 0)
    conn.commit()
    return stats


def load_artifact(conn, path: str) -> Dict[str, int]:
    """Replay a cross_court_judges.jsonl artifact (used by etl-promoter)."""
    return load_records(conn, read_artifact(path))


def extract_pending(
    conn,
    *,
    limit_rs: int = 2000,
    limit_echr: int = 2000,
    out_path: Optional[str] = None,
    load: bool = True,
) -> Dict[str, Any]:
    """Extract judges for recent RS and ECHR cases that have no case_judge rows yet."""
    records: List[JudgeRecord] = []

    if limit_rs > 0:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT c.ecli, ct.fulltext
                  FROM {SCHEMA}.cases c
                  JOIN {SCHEMA}.case_text ct ON ct.case_id = c.id AND ct.source = 'RECHTSPRAAK'
                 WHERE c.ecli LIKE 'ECLI:NL:%%'
                   AND ct.fulltext IS NOT NULL
                   AND NOT EXISTS (
                       SELECT 1 FROM {SCHEMA}.case_judge cj WHERE cj.case_id = c.id
                   )
                 ORDER BY c.date_decision DESC NULLS LAST, c.id DESC
                 LIMIT %s
                """,
                (limit_rs,),
            )
            rs_rows = cur.fetchall()
        conn.rollback()
        for ecli, fulltext in rs_rows:
            records.extend(extract_rs_judges(fulltext, ecli))

    if limit_echr > 0:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT DISTINCT ON (c.id) c.ecli, ct.fulltext
                  FROM {SCHEMA}.cases c
                  JOIN {SCHEMA}.case_text ct ON ct.case_id = c.id AND ct.source = 'HUDOC'
                 WHERE c.ecli LIKE 'ECLI:CE:ECHR:%%'
                   AND ct.fulltext IS NOT NULL
                   AND NOT EXISTS (
                       SELECT 1 FROM {SCHEMA}.case_judge cj WHERE cj.case_id = c.id
                   )
                 ORDER BY c.id DESC, (ct.language = 'en') DESC
                 LIMIT %s
                """,
                (limit_echr,),
            )
            echr_rows = cur.fetchall()
        conn.rollback()
        for ecli, fulltext in echr_rows:
            records.extend(extract_echr_judges(fulltext, ecli))

    if out_path:
        write_artifact(out_path, records)

    load_stats = load_records(conn, records) if load and records else {}
    by_dataset: Dict[str, int] = {}
    for rec in records:
        by_dataset[rec.source_dataset] = by_dataset.get(rec.source_dataset, 0) + 1
    return {
        "extracted_records": len(records),
        "by_dataset": by_dataset,
        "load": load_stats,
    }


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Extract RS and ECHR judges into cle_v2.case_judge")
    parser.add_argument("--limit-rs", type=int, default=2000)
    parser.add_argument("--limit-echr", type=int, default=2000)
    parser.add_argument("--out", default=None)
    parser.add_argument("--no-load", action="store_true")
    args = parser.parse_args(argv)

    from data_loading.clients.postgres import PostgresCLEClient

    with PostgresCLEClient() as client:
        summary = extract_pending(
            client._get_conn(),
            limit_rs=args.limit_rs,
            limit_echr=args.limit_echr,
            out_path=args.out,
            load=not args.no_load,
        )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
