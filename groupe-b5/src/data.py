"""Chargement des données de contacts (SocioPatterns) et construction du graphe.

Deux formats de fichiers sont gérés :
  1. le format brut SocioPatterns (.dat / .csv / .gz) : une ligne = "t i j" (+ "Ci Cj")
     où [t-20s, t] est l'intervalle de 20 secondes pendant lequel i et j étaient en contact ;
  2. le format Netzschleuder (.zip) : edges.csv (source, target, time) + nodes.csv.

On agrège ensuite tous les contacts en UN graphe statique non orienté :
  - un nœud = une personne,
  - une arête = au moins `min_contacts` intervalles de 20 s passés ensemble,
  - le poids de l'arête = nombre d'intervalles de 20 s en contact.
"""
from __future__ import annotations

import io
import json
import warnings
import zipfile
from collections import Counter
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd


# ----------------------------------------------------------------------------
# 1. Lecture des fichiers de contacts
# ----------------------------------------------------------------------------
def _read_socio_raw(path):
    """Format brut SocioPatterns : colonnes séparées par des espaces ou des tabulations."""
    try:
        df = pd.read_csv(path, sep=r"\s+", header=None, compression="infer")
    except pd.errors.EmptyDataError:
        raise ValueError(f"{path} : fichier vide") from None
    except pd.errors.ParserError as err:
        raise ValueError(f"{path} : format illisible ({err})") from None
    if df.shape[1] < 3:
        raise ValueError(f"{path} : il faut au moins 3 colonnes (t i j)")
    ncols = 5 if df.shape[1] >= 5 else 3
    df = df.iloc[:, :ncols].copy()
    df.columns = ["t", "i", "j", "gi", "gj"][:ncols]

    before = len(df)
    df = df.dropna(subset=["t", "i", "j"])           # données manquantes : lignes ignorées
    if len(df) < before:
        warnings.warn(f"{path} : {before - len(df)} ligne(s) incomplète(s) ignorée(s)")
    try:
        df["i"] = df["i"].astype(int)
        df["j"] = df["j"].astype(int)
    except (ValueError, TypeError):
        raise ValueError(f"{path} : les colonnes i et j doivent contenir des identifiants entiers") from None
    if df.empty:
        raise ValueError(f"{path} : aucun contact exploitable")

    groups = {}
    if ncols == 5:  # colonnes Ci / Cj : classe (école) ou statut (hôpital)
        for who, grp in zip(df["i"], df["gi"]):
            groups[int(who)] = str(grp)
        for who, grp in zip(df["j"], df["gj"]):
            groups[int(who)] = str(grp)
    return df[["t", "i", "j"]], groups


def _read_nz_csv(raw: bytes) -> pd.DataFrame:
    """Les CSV de Netzschleuder ont un en-tête qui commence par '# '."""
    lines = raw.decode("utf-8").splitlines()
    header = [c.strip() for c in lines[0].lstrip("#").split(",")]
    return pd.read_csv(io.StringIO("\n".join(lines[1:])), header=None, names=header)


def _read_netzschleuder(path):
    try:
        with zipfile.ZipFile(path) as z:
            names = {Path(n).name: n for n in z.namelist()}
            if "edges.csv" not in names:
                raise ValueError(f"{path} : pas de edges.csv dans l'archive ({list(names)})")
            edges = _read_nz_csv(z.read(names["edges.csv"]))
            nodes = _read_nz_csv(z.read(names["nodes.csv"])) if "nodes.csv" in names else None
    except zipfile.BadZipFile:
        raise ValueError(f"{path} : archive zip invalide ou corrompue (téléchargement interrompu ?)") from None
    if not {"source", "target"} <= set(edges.columns):
        raise ValueError(f"{path} : edges.csv doit avoir les colonnes source et target ({list(edges.columns)})")

    src, dst = edges["source"], edges["target"]
    groups = {}
    if nodes is not None:
        idx_col = "index" if "index" in nodes.columns else nodes.columns[0]
        label = nodes["id"] if "id" in nodes.columns else nodes[idx_col]
        mapping = dict(zip(nodes[idx_col], label))
        src, dst = src.map(mapping), dst.map(mapping)
        extra = [c for c in nodes.columns if c not in (idx_col, "id")]
        if extra:  # première colonne en plus = statut / classe
            groups = {int(a): str(g) for a, g in zip(label, nodes[extra[0]])}
    t = edges["time"] if "time" in edges.columns else pd.Series(np.zeros(len(edges)))
    try:
        df = pd.DataFrame({"t": t, "i": src.astype(int), "j": dst.astype(int)})
    except (ValueError, TypeError):
        raise ValueError(f"{path} : identifiants de nœuds manquants ou non entiers") from None
    if df.empty:
        raise ValueError(f"{path} : aucun contact exploitable")
    return df, groups


def load_contacts(path):
    """Renvoie (DataFrame ['t','i','j'], dict {personne: groupe})."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"{path} introuvable. Télécharge le jeu de données (voir README.md, "
            "section 'Données') ou utilise --synthetic pour un test rapide."
        )
    if path.suffix == ".zip":
        return _read_netzschleuder(path)
    return _read_socio_raw(path)


# ----------------------------------------------------------------------------
# 2. Construction du graphe statique
# ----------------------------------------------------------------------------
def build_graph(contacts: pd.DataFrame, groups: dict | None = None, min_contacts: int = 1) -> nx.Graph:
    """Agrège les contacts en un graphe pondéré.

    poids(i, j) = nombre d'intervalles de 20 s en contact.
    On garde les arêtes dont le poids est >= min_contacts (ça enlève les contacts
    très brefs, probablement peu contaminants). Tous les individus restent dans
    le graphe, même ceux qui deviennent isolés.
    """
    groups = groups or {}
    pairs = Counter(
        (min(a, b), max(a, b)) for a, b in zip(contacts["i"], contacts["j"]) if a != b
    )
    G = nx.Graph()
    people = set(contacts["i"]) | set(contacts["j"]) | set(groups)
    G.add_nodes_from(sorted(int(p) for p in people))
    for (a, b), w in pairs.items():
        if w >= min_contacts:
            G.add_edge(int(a), int(b), weight=int(w))
    for v in G.nodes:
        G.nodes[v]["group"] = groups.get(v, "?")
    return G


def load_graph(path, min_contacts: int = 1) -> nx.Graph:
    contacts, groups = load_contacts(path)
    return build_graph(contacts, groups, min_contacts)


# ----------------------------------------------------------------------------
# 3. Graphe synthétique (SEULEMENT pour les tests et le développement)
# ----------------------------------------------------------------------------
def synthetic_graph(n_groups=4, group_size=20, p_in=0.35, p_out=0.01, seed=0) -> nx.Graph:
    """Petit réseau avec des communautés (modèle SBM) qui ressemble à une école.

    A utiliser pour tester le code sans les vraies données. Les résultats du
    rapport doivent bien sûr venir des vraies données SocioPatterns.
    """
    sizes = [group_size] * n_groups
    probs = [[p_in if a == b else p_out for b in range(n_groups)] for a in range(n_groups)]
    sbm = nx.stochastic_block_model(sizes, probs, seed=seed)
    rng = np.random.default_rng(seed)
    G = nx.Graph()
    G.add_nodes_from(sbm.nodes)
    for u, v in sbm.edges:
        G.add_edge(u, v, weight=int(rng.integers(1, 15)))
    for v in G.nodes:
        G.nodes[v]["group"] = f"G{sbm.nodes[v]['block']}"
    return G


# ----------------------------------------------------------------------------
# 4. Sauvegarde / lecture du graphe en JSON (lu aussi par le vérificateur)
# ----------------------------------------------------------------------------
def save_graph_json(G: nx.Graph, path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "nodes": sorted(int(v) for v in G.nodes),
        "edges": [[int(u), int(v), int(d.get("weight", 1))] for u, v, d in G.edges(data=True)],
        "groups": {str(v): G.nodes[v].get("group", "?") for v in G.nodes},
    }
    path.write_text(json.dumps(data), encoding="utf-8")


def load_graph_json(path) -> nx.Graph:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    G = nx.Graph()
    G.add_nodes_from(data["nodes"])
    for u, v, w in data["edges"]:
        G.add_edge(u, v, weight=w)
    for v, g in data.get("groups", {}).items():
        G.nodes[int(v)]["group"] = g
    return G
