from data_loading.data_loader import _deduplicate_rows


class Processor:
    key_field = "ECLI"

    @staticmethod
    def _key(row):
        return row.get("ECLI")


def test_deduplicate_rows_uses_last_row_for_each_source_identity():
    rows = [
        {"ECLI": "ECLI:NL:TEST:1", "title": "old"},
        {"ECLI": "ECLI:NL:TEST:2", "title": "only"},
        {"ECLI": "ECLI:NL:TEST:1", "title": "new"},
    ]

    unique, missing = _deduplicate_rows(rows, Processor())

    assert missing == 0
    assert unique == [
        {"ECLI": "ECLI:NL:TEST:1", "title": "new"},
        {"ECLI": "ECLI:NL:TEST:2", "title": "only"},
    ]


def test_deduplicate_rows_reports_missing_identities():
    unique, missing = _deduplicate_rows(
        [{"ECLI": "ECLI:NL:TEST:1"}, {"ECLI": ""}, {}], Processor()
    )

    assert unique == [{"ECLI": "ECLI:NL:TEST:1"}]
    assert missing == 2
