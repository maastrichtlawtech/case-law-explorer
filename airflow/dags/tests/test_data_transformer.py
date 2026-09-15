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


def test_echr_transform_keeps_real_documents_without_ecli(tmp_path):
    source = tmp_path / "ECHR_metadata.csv"
    with source.open("w", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(
            target,
            fieldnames=["itemid", "ecli", "appno", "referencedate", "isplaceholder"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "itemid": "001-communicated",
                "ecli": "",
                "appno": "12345/26",
                "referencedate": "2026-07-03T00:00:00Z",
                "isplaceholder": "False",
            }
        )

    [result] = transform_data(
        caselaw_type="ECHR",
        input_paths=[str(source)],
        output_dir=str(tmp_path / "processed"),
    )

    with open(result, newline="", encoding="utf-8") as transformed:
        rows = list(csv.DictReader(transformed))
    assert len(rows) == 1
    assert rows[0]["document_id"] == "001-communicated"
    assert rows[0]["ECLI"] == ""
    assert rows[0]["reference_date"].startswith("2026-07-03")


def test_echr_transform_omits_press_releases_and_clinical_summaries(tmp_path):
    source = tmp_path / "ECHR_metadata.csv"
    with source.open("w", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=["itemid", "doctype"])
        writer.writeheader()
        writer.writerows(
            [
                {"itemid": "001-press", "doctype": "PR"},
                {"itemid": "001-clin", "doctype": "CLIN"},
                {"itemid": "001-judgment", "doctype": "JUD"},
            ]
        )

    [result] = transform_data(
        caselaw_type="ECHR",
        input_paths=[str(source)],
        output_dir=str(tmp_path / "processed"),
    )
    with open(result, newline="", encoding="utf-8") as transformed:
        rows = list(csv.DictReader(transformed))
    assert [row["document_id"] for row in rows] == ["001-judgment"]
