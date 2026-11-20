"""Tests du chargement des données (sur de petits fichiers fabriqués dans les deux formats)."""
import gzip
import zipfile

from src.data import build_graph, load_contacts, load_graph, load_graph_json, save_graph_json, synthetic_graph

RAW = (  # format SocioPatterns : t i j Ci Cj (séparés par des tabulations)
    "20\t1\t2\tA\tA\n"
    "40\t1\t2\tA\tA\n"
    "40\t2\t3\tA\tB\n"
    "60\t3\t4\tB\tB\n"
    "60\t3\t3\tB\tB\n"   # auto-contact : doit être ignoré
)


def test_load_raw_socio_file(tmp_path):
    f = tmp_path / "contacts.dat"
    f.write_text(RAW)
    G = load_graph(f)
    assert sorted(G.nodes) == [1, 2, 3, 4]
    assert G[1][2]["weight"] == 2          # 2 intervalles de 20 s ensemble
    assert G[2][3]["weight"] == 1
    assert not G.has_edge(3, 3)
    assert G.nodes[3]["group"] == "B"


def test_load_gzip_file(tmp_path):
    f = tmp_path / "contacts.dat.gz"
    with gzip.open(f, "wt") as fh:
        fh.write(RAW)
    assert load_graph(f).number_of_edges() == 3


def test_min_contacts_filters_weak_edges_but_keeps_people(tmp_path):
    f = tmp_path / "contacts.dat"
    f.write_text(RAW)
    contacts, groups = load_contacts(f)
    G = build_graph(contacts, groups, min_contacts=2)
    assert list(G.edges) == [(1, 2)]
    assert sorted(G.nodes) == [1, 2, 3, 4]   # 3 et 4 restent dans la population


def test_load_netzschleuder_zip(tmp_path):
    f = tmp_path / "sp.csv.zip"
    with zipfile.ZipFile(f, "w") as z:
        z.writestr("edges.csv", "# source,target,time\n0,1,20\n0,1,40\n1,2,40\n")
        z.writestr("nodes.csv", "# index,id,status\n0,101,MED\n1,102,NUR\n2,103,PAT\n")
    G = load_graph(f)
    assert sorted(G.nodes) == [101, 102, 103]
    assert G[101][102]["weight"] == 2
    assert G.nodes[103]["group"] == "PAT"


def test_missing_file_gives_helpful_message(tmp_path):
    try:
        load_graph(tmp_path / "nope.zip")
    except FileNotFoundError as e:
        assert "README" in str(e)
    else:
        raise AssertionError("FileNotFoundError attendue")


def test_json_roundtrip(tmp_path):
    G = synthetic_graph(seed=5)
    save_graph_json(G, tmp_path / "g.json")
    H = load_graph_json(tmp_path / "g.json")
    assert set(G.nodes) == set(H.nodes)
    assert {frozenset(e) for e in G.edges} == {frozenset(e) for e in H.edges}
    assert all(G[u][v]["weight"] == H[u][v]["weight"] for u, v in G.edges)
    assert all(G.nodes[v]["group"] == H.nodes[v]["group"] for v in G.nodes)
