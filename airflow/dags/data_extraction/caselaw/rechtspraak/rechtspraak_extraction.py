"""
Main RS extraction routine. Used by the rechtspaark_extraction DAG.
"""

import logging
import os
from datetime import datetime, timedelta

import pandas as pd
import rechtspraak_extractor.rechtspraak as rex
from definitions.storage_handler import CSV_RS_CASES
from dotenv import find_dotenv, load_dotenv
from rechtspraak_extractor.rechtspraak_metadata import (
    fetch_eclis_via_sqlite,
    get_rechtspraak_metadata,
)

env_file = find_dotenv()
load_dotenv(env_file, override=True)

# A base-feed summary this long or longer is treated as the actual judgment
# text rather than a short abstract. Rechtspraak's Atom feed sometimes embeds
# the full text there (short rulings/conclusies in particular), and using it
# means one less live per-ECLI call against an API with a history of
# rate-limiting at volume (issue #31).
FULL_TEXT_MIN_LENGTH = 1000

# lido.db carries these but rechtspraak_extractor's own METADATA_COLUMNS
# contract (used by get_rechtspraak_metadata's method="sqlite" path) doesn't
# include them, so they're fetched with a second, direct call -- otherwise
# case_law_reference would have nothing to read them from.
EXTRA_SQLITE_COLUMNS = ["legislations_cited", "bwb_id"]


def _daily_ranges(starting_date: str, ending_date: str):
    """Yield one-day API windows for every date in an inclusive range."""
    current_date = datetime.strptime(starting_date, "%Y-%m-%d")
    end_date = datetime.strptime(ending_date, "%Y-%m-%d")
    while current_date <= end_date:
        next_date = current_date + timedelta(days=1)
        yield current_date, next_date
        current_date = next_date


def _cap_base_extraction(base_extraction: pd.DataFrame | None, amount: int):
    """Enforce the caller's document cap on the extractor's returned page.

    rechtspraak_extractor currently fetches Atom pages in batches of 1,000.
    It stops once the requested count is reached, but returns the whole final
    page instead of truncating it.  A 25-document pilot can therefore flow on
    as 1,000 metadata requests and database upserts unless the DAG guards the
    boundary itself.
    """
    if base_extraction is None or len(base_extraction) <= amount:
        return base_extraction

    logging.warning(
        "rechtspraak_extractor returned %s rows for max_ecli=%s; "
        "truncating to the requested limit",
        len(base_extraction),
        amount,
    )
    return base_extraction.head(amount).copy()


def _lido_sqlite_db_path(lido_sqlite_db_path: str | None) -> str:
    if lido_sqlite_db_path:
        return lido_sqlite_db_path
    from lido_sqlite_paths import get_lido_sqlite_paths

    _, db_path = get_lido_sqlite_paths()
    return str(db_path)


def _fetch_extra_sqlite_columns(eclis: list, sqlite_db_path: str) -> pd.DataFrame:
    eclis = sorted({e for e in eclis if isinstance(e, str) and e})
    if not eclis:
        return pd.DataFrame(columns=["ecli", *EXTRA_SQLITE_COLUMNS])
    return fetch_eclis_via_sqlite(
        ecli_list=eclis,
        sqlite_db_path=sqlite_db_path,
        columns=["ecli", *EXTRA_SQLITE_COLUMNS],
    )


def _looks_like_full_text(value) -> bool:
    return isinstance(value, str) and len(value) >= FULL_TEXT_MIN_LENGTH


def _is_missing_full_text(series: pd.Series) -> pd.Series:
    return series.isna() | (series == "")


def _backfill_full_text(
    metadata_df: pd.DataFrame, base_extraction: pd.DataFrame, output_dir: str
) -> pd.DataFrame:
    """full_text is never in lido.db (the LIDO bulk export doesn't carry
    judgment text), so every sqlite-sourced row leaves it empty. Try the base
    feed's own summary first -- it sometimes already holds the full judgment
    -- and fall back to a second, narrower live API call only for whatever's
    still missing after that, rather than calling the live API unconditionally
    for every row."""
    if metadata_df.empty or "full_text" not in metadata_df.columns:
        return metadata_df

    missing = _is_missing_full_text(metadata_df["full_text"])
    if not missing.any():
        return metadata_df

    if (
        base_extraction is not None
        and not base_extraction.empty
        and "summary" in base_extraction.columns
    ):
        summaries = (
            base_extraction[["id", "summary"]]
            .dropna(subset=["id"])
            .drop_duplicates("id")
            .rename(columns={"id": "ecli"})
        )
        usable = summaries.set_index("ecli")["summary"]
        usable = usable[usable.apply(_looks_like_full_text)]
        fill_from_base = metadata_df["ecli"].map(usable)
        metadata_df["full_text"] = metadata_df["full_text"].mask(
            missing & fill_from_base.notna(), fill_from_base
        )
        missing = _is_missing_full_text(metadata_df["full_text"])

    if not missing.any() or base_extraction is None or base_extraction.empty:
        return metadata_df

    still_missing_eclis = metadata_df.loc[missing, "ecli"].tolist()
    subset = base_extraction[base_extraction["id"].isin(still_missing_eclis)]
    if subset.empty:
        return metadata_df

    live_df = get_rechtspraak_metadata(
        save_file="n", dataframe=subset, _fake_headers=True, data_dir=output_dir, method="api"
    )
    if live_df is None or live_df.empty or "full_text" not in live_df.columns:
        return metadata_df

    live_full_text = (
        live_df.dropna(subset=["ecli"]).drop_duplicates("ecli").set_index("ecli")["full_text"]
    )
    fill_from_live = metadata_df["ecli"].map(live_full_text)
    metadata_df["full_text"] = metadata_df["full_text"].mask(
        missing & fill_from_live.notna(), fill_from_live
    )
    return metadata_df


def rechtspraak_extract(
    starting_date: str,
    ending_date: str,
    amount: int,
    output_dir: str,
    skip_if_exists: bool = True,
    lido_sqlite_db_path: str | None = None,
) -> dict:
    """
    Extracts Rechtspraak data for the given date range and saves outputs in output_dir.
    Returns a dict with paths to base, metadata, and citation files.
    """
    # Prepare output file paths
    base_file = os.path.join(output_dir, "base_extraction_rechtspraak.csv")
    metadata_file = os.path.join(output_dir, "metadata_extraction_rechtspraak.csv")
    citation_file = os.path.join(output_dir, CSV_RS_CASES)

    # Check if all outputs exist
    if skip_if_exists and all(os.path.exists(f) for f in [base_file, metadata_file, citation_file]):
        logging.info(f"All output files exist in {output_dir}, skipping extraction.")
        return {"base": base_file, "metadata": metadata_file, "citations": citation_file}

    sqlite_db_path = _lido_sqlite_db_path(lido_sqlite_db_path)

    os.makedirs(output_dir, exist_ok=True)
    metadata_df_list = []
    # Extract per day in the range
    for current_date, next_date in _daily_ranges(starting_date, ending_date):
        logging.info(f"Processing date range: {current_date.date()} - {next_date.date()}")
        base_extraction = rex.get_rechtspraak(
            max_ecli=amount, sd=str(current_date.date()), ed=str(next_date.date()), save_file="n"
        )
        base_extraction = _cap_base_extraction(base_extraction, amount)
        # Store the dataframe for the current date
        base_file_day = os.path.join(output_dir, f"base_{current_date.date()}.csv")
        if base_extraction is not None:
            base_extraction.to_csv(base_file_day, index=False)
        # SQLite first (built from the monthly LIDO export by lido_sqlite_build),
        # live per-ECLI API only as a fallback for ECLIs missing from it
        # entirely -- e.g. very recent cases published since the last refresh.
        metadata_df = get_rechtspraak_metadata(
            save_file="n",
            dataframe=base_extraction,
            _fake_headers=True,
            data_dir=output_dir,
            method="sqlite",
            sqlite_db_path=sqlite_db_path,
            fallback_to_api=True,
        )
        if metadata_df is not None and not metadata_df.empty:
            eclis = base_extraction["id"].tolist() if base_extraction is not None else []
            extra_df = _fetch_extra_sqlite_columns(eclis, sqlite_db_path)
            if not extra_df.empty:
                metadata_df = metadata_df.merge(extra_df, on="ecli", how="left")
            metadata_df = _backfill_full_text(metadata_df, base_extraction, output_dir)
        metadata_file_day = os.path.join(output_dir, f"metadata_{current_date.date()}.csv")
        if metadata_df is not None:
            metadata_df.to_csv(metadata_file_day, index=False)
            metadata_df_list.append(metadata_df)
    # Concatenate all metadata
    if metadata_df_list:
        metadata_df = pd.concat(metadata_df_list, ignore_index=True)
        metadata_df.to_csv(metadata_file, index=False)
    else:
        metadata_df = pd.DataFrame()
        metadata_df.to_csv(metadata_file, index=False)
    # Concatenate all base extractions
    base_files = [
        os.path.join(output_dir, f)
        for f in os.listdir(output_dir)
        if f.startswith("base_") and f.endswith(".csv")
    ]
    if base_files:
        base_df = pd.concat([pd.read_csv(f) for f in base_files], ignore_index=True)
        base_df.to_csv(base_file, index=False)
    else:
        base_df = pd.DataFrame()
        base_df.to_csv(base_file, index=False)

    # Carry the title across from the base extraction.
    #
    # Only the base feed has one; the metadata API does not return a title at
    # all, and the loader reads the metadata frame, so cases.title was null for
    # every Rechtspraak row while the title sat in a file the run deleted on its
    # way out. The base feed's "id" is the ECLI, so this joins on identity.
    if not metadata_df.empty and not base_df.empty and "title" in base_df.columns:
        titles = base_df[["id", "title"]].dropna(subset=["id"]).drop_duplicates("id")
        metadata_df = metadata_df.merge(
            titles.rename(columns={"id": "ecli"}), on="ecli", how="left"
        )

    # No live LIDO citations-API call. citations_outgoing/legislations_cited
    # come from lido.db (built monthly by lido_sqlite_build from the same
    # LIDO export), read above alongside the metadata itself -- resolving them
    # a second time over the LIDO web service would be asking a remote API for
    # data already held locally.
    metadata_df.to_csv(citation_file, index=False)
    return {"base": base_file, "metadata": metadata_file, "citations": citation_file}
