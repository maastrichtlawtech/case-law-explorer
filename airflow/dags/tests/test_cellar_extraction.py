from data_extraction.caselaw.cellar.cellar_extraction import (
    _artifacts_complete,
    _write_lines,
)


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
