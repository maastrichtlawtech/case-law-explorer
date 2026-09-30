from data_loading.citation_graph_loader import _load_edge_file


class RecordingClient:
    def __init__(self):
        self.rows = []

    def resolve_case_id(self, *, ecli=None, celex_id=None):
        if celex_id:
            return {"62026CJ0001": 30, "62025CJ0002": 31}.get(celex_id)
        return {"ECLI:CE:ECHR:2026:SOURCE": 11, "ECLI:CE:ECHR:2025:TARGET": 20}.get(
            ecli
        )

    def resolve_case_id_by_item_id(self, item_id):
        return {"001-source": 10, "001-target": 21}.get(item_id)

    def upsert_citation(self, **row):
        self.rows.append(row)


def test_echr_edges_resolve_ecli_and_item_id_identifiers(tmp_path):
    path = tmp_path / "ECHR_edges.txt"
    path.write_text(
        "001-source,ECLI:CE:ECHR:2025:TARGET\n"
        "ECLI:CE:ECHR:2026:SOURCE,001-target\n"
        "001-source,001-unknown\n",
        encoding="utf-8",
    )
    client = RecordingClient()

    loaded = _load_edge_file(client, str(path), "echr", "ECHR")

    assert loaded == 3
    assert [row["source_case_id"] for row in client.rows] == [10, 11, 10]
    assert [row["target_case_id"] for row in client.rows] == [20, 21, None]
    assert client.rows[2]["target_ecli_raw"] == "001-unknown"
    assert path.exists()


def test_cellar_edges_still_resolve_celex(tmp_path):
    path = tmp_path / "cellar_edges.txt"
    path.write_text("62026CJ0001,62025CJ0002\n", encoding="utf-8")
    client = RecordingClient()

    loaded = _load_edge_file(client, str(path), "celex", "EURLEX")

    assert loaded == 1
    assert client.rows[0]["source_case_id"] == 30
    assert client.rows[0]["target_case_id"] == 31
    assert path.exists()
