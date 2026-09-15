from data_extraction.caselaw.cellar.cellar_extraction import (
    _artifacts_complete,
    _full_text_case_coverage,
    _write_lines,
)
import pandas as pd


def test_artifacts_complete_requires_every_output(tmp_path):
    paths = {
        name: str(tmp_path / filename)
        for name, filename in {
            "metadata": "cellar.csv",
            "full_text": "cellar_full_text.json",
            "nodes": "cellar_nodes.txt",
            "edges": "cellar_edges.txt",
        }.items()
    }

    for path in paths.values():
        open(path, "w").close()

    assert _artifacts_complete(paths)

    (tmp_path / "cellar_full_text.json").unlink()

    assert not _artifacts_complete(paths)


def test_write_lines_materializes_empty_graph_artifacts(tmp_path):
    nodes_path = tmp_path / "nodes.txt"
    edges_path = tmp_path / "edges.txt"

    _write_lines(nodes_path, False)
    _write_lines(edges_path, [])

    assert nodes_path.is_file()
    assert nodes_path.read_text() == ""
    assert edges_path.is_file()
    assert edges_path.read_text() == ""


def test_full_text_case_coverage_counts_one_translation_per_case():
    metadata = pd.DataFrame(
        [{"celex": "62026CJ0001"}, {"celex": "62026CJ0002"}]
    )
    texts = [
        {"celex": "62026CJ0001;62026CJ0001_RES", "text_language": "EN", "text": "body"},
        {"celex": "62026CJ0001", "text_language": "FR", "text": "corps"},
        {"celex": "62026CJ0002", "text_language": "EN", "text": ""},
    ]

    assert _full_text_case_coverage(metadata, texts) == 0.5
