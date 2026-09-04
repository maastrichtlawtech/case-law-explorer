"""
Contains the method 'drop_columns'. Used by cellar extraction to reduce the
extractor's output to the cases and columns this pipeline stores.

Rewritten for cellar-extractor 2.x. Until then this held three lists of the raw
CDM predicate labels the old SPARQL output carried, and dropped by exclusion:
everything named in them that was not also named in a keep list. 2.x emits a
fixed canonical schema instead of a raw predicate dump, so keeping by inclusion
is both shorter and self-maintaining - the columns worth keeping are exactly the
ones the transformer knows how to read, and that list already exists as
MAP_CELLAR.
"""

import glob

from data_transformation.utils import read_csv
from definitions.mappings.attribute_name_maps import MAP_CELLAR
from definitions.storage_handler import DIR_DATA_PROCESSED

# The columns the transformer reads. Anything else the extractor produces is
# dropped here so the intermediate CSV stays the width of what we store.
COLUMNS_TO_KEEP = set(MAP_CELLAR)


def drop_columns(data):
    """Reduce an extractor frame in place to CJEU case law and stored columns.

    Named for what it did rather than what it does; the callers are unchanged.
    """
    for column in [c for c in data.columns if c not in COLUMNS_TO_KEEP]:
        data.pop(column)

    # Keep every document from the EU courts (Court of Justice, General Court,
    # and any other EU-court designator), while excluding national/EFTA ECLIs.
    # Sector 6 below already identifies case-law documents, so filtering again
    # by resource_type would silently discard Orders and other valid case data.
    data.drop(data[~data["ecli"].str.startswith("ECLI:EU:", na=False)].index, inplace=True)

    # Sector 6 is case law. Note this also discards the sector 3 legislation
    # that cellar-extractor 2.x added support for: if that is wanted in
    # cle_v2, this is the line that decides it.
    data.drop(data[~data["celex"].str.startswith("6", na=False)].index, inplace=True)

    data.reset_index(inplace=True, drop=True)


if __name__ == "__main__":
    print("")
    print("TRANSFORMATION OF CSV FILES IN DATA PROCESSED DIR STARTED")
    print("")
    csv_files = glob.glob(DIR_DATA_PROCESSED + "/" + "*.csv")
    for csv_file in csv_files:
        if "test" in csv_file:
            read_csv(csv_file)
    print("")
    print("TRANSFORMATION DONE")
    print("")
