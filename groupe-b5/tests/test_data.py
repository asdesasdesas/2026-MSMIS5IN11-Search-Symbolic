"""Tests du chargement des données (sur de petits fichiers fabriqués dans les deux formats)."""
import gzip
import zipfile

from src.data import build_graph, load_contacts, load_graph, load_graph_json, save_graph_json, synthetic_graph

# on fabrique un mini-fichier SocioPatterns : chaque ligne représente une rencontre à un instant, avec les groupes des personnes
RAW = (  # format SocioPatterns : t i j Ci Cj (séparés par des tabulations)
    "20\t1\t2\tA\tA\n"
    "40\t1\t2\tA\tA\n"
    "40\t2\t3\tA\tB\n"
    "60\t3\t4\tB\tB\n"
    "60\t3\t3\tB\tB\n"   # auto-contact : doit être ignoré
)


# on contrôle le chargement du format brut : nœuds, poids des liens, contacts invalides et catégories
def test_load_raw_socio_file(tmp_path):
    f = tmp_path / "contacts.dat"
    f.write_text(RAW)
    # le chargeur lit le petit fichier et agrège les interactions en arêtes pondérées
    G = load_graph(f)
    assert sorted(G.nodes) == [1, 2, 3, 4]
    assert G[1][2]["weight"] == 2          # 2 intervalles de 20 s ensemble
    assert G[2][3]["weight"] == 1
    assert not G.has_edge(3, 3)
    assert G.nodes[3]["group"] == "B"


# même principe mais avec un fichier compressé .gz, comme les données réelles téléchargées
def test_load_gzip_file(tmp_path):
    f = tmp_path / "contacts.dat.gz"
    with gzip.open(f, "wt") as fh:
        fh.write(RAW)
    assert load_graph(f).number_of_edges() == 3


# un seuil de 2 supprime les contacts de 20 s, sans faire disparaître les personnes isolées
def test_min_contacts_filters_weak_edges_but_keeps_people(tmp_path):
    f = tmp_path / "contacts.dat"
    f.write_text(RAW)
    # on sépare la lecture des contacts de la construction du graphe pour tester le seuil
    contacts, groups = load_contacts(f)
    G = build_graph(contacts, groups, min_contacts=2)
    assert list(G.edges) == [(1, 2)]
    assert sorted(G.nodes) == [1, 2, 3, 4]   # 3 et 4 restent dans la population


# le projet sait aussi charger un ZIP contenant un fichier de liens et un fichier de nœuds
def test_load_netzschleuder_zip(tmp_path):
    f = tmp_path / "sp.csv.zip"
    # on construit l’archive directement dans le test : aucune donnée réelle n’est nécessaire
    with zipfile.ZipFile(f, "w") as z:
        z.writestr("edges.csv", "# source,target,time\n0,1,20\n0,1,40\n1,2,40\n")
        z.writestr("nodes.csv", "# index,id,status\n0,101,MED\n1,102,NUR\n2,103,PAT\n")
    G = load_graph(f)
    assert sorted(G.nodes) == [101, 102, 103]
    assert G[101][102]["weight"] == 2
    assert G.nodes[103]["group"] == "PAT"


# on vérifie qu’un fichier absent provoque une erreur compréhensible qui renvoie vers le README
def test_missing_file_gives_helpful_message(tmp_path):
    try:
        load_graph(tmp_path / "nope.zip")
    # une bonne erreur est attendue : si elle survient, on vérifie son message
    except FileNotFoundError as e:
        assert "README" in str(e)
    else:
        raise AssertionError("FileNotFoundError attendue")


# on sauvegarde un graphe puis on le recharge : toutes les informations importantes doivent rester identiques
def test_json_roundtrip(tmp_path):
    G = synthetic_graph(seed=5)
    # on écrit dans tmp_path pour ne pas créer de fichier définitif
    save_graph_json(G, tmp_path / "g.json")
    H = load_graph_json(tmp_path / "g.json")
    assert set(G.nodes) == set(H.nodes)
    assert {frozenset(e) for e in G.edges} == {frozenset(e) for e in H.edges}
    assert all(G[u][v]["weight"] == H[u][v]["weight"] for u, v in G.edges)
    assert all(G.nodes[v]["group"] == H.nodes[v]["group"] for v in G.nodes)
