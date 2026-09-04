import csv

from data_transformation.data_transformer import transform_data


def test_echr_transform_omits_language_placeholders(tmp_path):
    source = tmp_path / "ECHR_metadata.csv"
    with source.open("w", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(
            target,
            fieldnames=[
                "itemid",
                "ecli",
                "docname",
                "languageisocode",
                "isplaceholder",
            ],
        )
        writer.writeheader()
        writer.writerows(
            [
                {
                    "itemid": "001-placeholder",
                    "ecli": "ECLI:CE:ECHR:2026:TEST",
                    "docname": "Unavailable in English",
                    "languageisocode": "ENG",
                    "isplaceholder": "True",
                },
                {
                    "itemid": "001-real",
                    "ecli": "ECLI:CE:ECHR:2026:TEST",
                    "docname": "Disponible en français",
                    "languageisocode": "FRE",
                    "isplaceholder": "False",
                },
            ]
        )

    [result] = transform_data(
        caselaw_type="ECHR",
        input_paths=[str(source)],
        output_dir=str(tmp_path / "processed"),
    )

    with open(result, newline="", encoding="utf-8") as transformed:
        rows = list(csv.DictReader(transformed))
    assert [row["document_id"] for row in rows] == ["001-real"]
