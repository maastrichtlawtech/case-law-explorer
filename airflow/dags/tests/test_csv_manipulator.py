import pandas as pd

from helpers.csv_manipulator import drop_columns


def test_drop_columns_keeps_all_eu_sector_6_case_documents():
    data = pd.DataFrame(
        [
            {
                "ecli": "ECLI:EU:C:2026:1",
                "celex": "62026CJ0001",
                "resource_type": "Judgment",
                "unused": "drop me",
            },
            {
                "ecli": "ECLI:EU:T:2026:2",
                "celex": "62026TO0002",
                "resource_type": "Order",
                "unused": "drop me",
            },
            {
                "ecli": "ECLI:EFTA:2026:3",
                "celex": "62026XX0003",
                "resource_type": "Judgment",
                "unused": "drop me",
            },
            {
                "ecli": "ECLI:EU:C:2026:4",
                "celex": "32026R0004",
                "resource_type": "Regulation",
                "unused": "drop me",
            },
        ]
    )

    drop_columns(data)

    assert data[["ecli", "resource_type"]].to_dict("records") == [
        {"ecli": "ECLI:EU:C:2026:1", "resource_type": "Judgment"},
        {"ecli": "ECLI:EU:T:2026:2", "resource_type": "Order"},
    ]
    assert "unused" not in data.columns
