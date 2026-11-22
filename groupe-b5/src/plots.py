"""Graphiques pour le notebook et le rapport."""
from __future__ import annotations
from matplotlib.transforms import Bbox

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np

# Table de style partagée par toutes les figures : une méthode garde la même
# couleur et le même marqueur partout, ce qui permet de la repérer d'un graphique à l'autre.
STYLES = {  # une couleur / un marqueur par méthode, pour que les figures soient lisibles
    "random": ("tab:gray", "x"),
    "degree": ("tab:blue", "o"),
    "betweenness": ("tab:orange", "s"),
    "pagerank": ("tab:purple", "^"),
    "closeness": ("navy", "<"),
    "kcore": ("darkgoldenrod", ">"),
    "greedy": ("tab:green", "D"),
    "ilp": ("tab:red", "*"),
    "ilp_deg": ("tab:brown", "P"),
    "strength": ("tab:cyan", "v"),
    "greedy_edges": ("tab:olive", "d"),
    "ilp_edges": ("tab:pink", "h"),
}
# Pour une méthode absente de la table, les fonctions ci-dessous utilisent
# STYLES.get(méthode, (None, "o")) : couleur automatique de matplotlib, marqueur rond.

# Décalages (en points) utilisés à tour de rôle pour que deux étiquettes voisines ne se chevauchent pas
# Positions d'étiquette essayées dans l'ordre : (décalage x, décalage y en points, alignement horizontal, vertical)
_CANDIDATES = [
    (8, 6, "left", "bottom"), (8, -6, "left", "top"),
    (-8, 6, "right", "bottom"), (-8, -6, "right", "top"),
    (0, 10, "center", "bottom"), (0, -10, "center", "top"),
    (18, 20, "left", "bottom"), (18, -20, "left", "top"),
    (-18, 20, "right", "bottom"), (-18, -20, "right", "top"),
    (0, 28, "center", "bottom"), (0, -28, "center", "top"),
]


def _label_points(ax, points, fontsize=8):
    """Écrit le nom de chaque méthode près de son point, sans chevauchement.

    À appeler EN DERNIER (après les échelles, les titres et tight_layout), car la
    place disponible se calcule sur le graphique tel qu'il sera dessiné.
    Les méthodes aux valeurs (x, y) identiques partagent une seule étiquette.
    """
    groups = {}
    for x, y, name in points:
        groups.setdefault((round(float(x), 6), round(float(y), 6)), []).append(name)
    fig = ax.figure
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    axbox = ax.get_window_extent(renderer)
    keys = sorted(groups)
    pad = 7 * fig.dpi / 72
    # zones déjà occupées : d'abord tous les marqueurs, puis les étiquettes posées
    taken = [Bbox([[px - pad, py - pad], [px + pad, py + pad]]) for px, py in ax.transData.transform(keys)]
    for key in keys:
        text = "\n".join(groups[key])
        best = None  # (score, candidat, zone)
        for cand in _CANDIDATES:
            dx, dy, ha, va = cand
            ann = ax.annotate(text, key, textcoords="offset points", xytext=(dx, dy),
                              fontsize=fontsize, ha=ha, va=va)
            box = ann.get_window_extent(renderer)
            ann.remove()
            inside = (axbox.x0 <= box.x0 and box.x1 <= axbox.x1 and
                      axbox.y0 <= box.y0 and box.y1 <= axbox.y1)
            score = sum(box.overlaps(t) for t in taken) + (0 if inside else 100)
            if best is None or score < best[0]:
                best = (score, cand, box)
            if score == 0:
                break
        _, (dx, dy, ha, va), box = best
        ax.annotate(text, key, textcoords="offset points", xytext=(dx, dy),
                    fontsize=fontsize, ha=ha, va=va)
        taken.append(box)

def plot_attack_rate(df, baseline: float, path=None, title="Taux d'attaque selon la méthode"):
    """Taux d'attaque moyen (fraction de la population infectée) en fonction de k."""
    fig, ax = plt.subplots(figsize=(7, 4.5))
    # une courbe par méthode : groupby sépare le tableau en un sous-tableau par méthode
    for method, sub in df.groupby("method"):
        color, marker = STYLES.get(method, (None, "o"))
        sub = sub.sort_values("k")  # on trie par k pour que la ligne ne zigzague pas
        ax.plot(sub["k"], sub["attack_mean"], marker=marker, color=color, label=method)
    # ligne horizontale de référence : taux d'attaque sans aucune intervention
    ax.axhline(baseline, color="black", linestyle="--", label="sans intervention")
    ax.set_xlabel("k = nombre de personnes ciblées")
    ax.set_ylabel("taux d'attaque moyen (SIR)")
    ax.set_title(title)
    ax.legend(loc="lower left", fontsize=8)
    ax.grid(alpha=0.3)  # grille discrète
    fig.tight_layout()  # évite que les étiquettes soient coupées
    if path:  # on n'enregistre que si un chemin est fourni
        fig.savefig(path, dpi=150)
    return fig  # renvoyée pour pouvoir l'afficher dans un notebook


def plot_major_outbreak(df, baseline_p: float, path=None):
    """Probabilité d'épidémie majeure (taux d'attaque >= seuil) en fonction de k."""
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for method, sub in df.groupby("method"):
        color, marker = STYLES.get(method, (None, "o"))
        sub = sub.sort_values("k")
        ax.plot(sub["k"], sub["p_major"], marker=marker, color=color, label=method)
    # probabilité d'épidémie majeure sans intervention, pour comparaison
    ax.axhline(baseline_p, color="black", linestyle="--", label="sans intervention")
    ax.set_xlabel("k = nombre de personnes ciblées")
    ax.set_ylabel("probabilité d'épidémie majeure")
    ax.set_title("Probabilité qu'une épidémie démarre vraiment")
    ax.set_ylim(0, 1.02)  # axe borné : c'est une probabilité (marge de 0.02 en haut pour la lisibilité)
    ax.legend(loc="lower left", fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    if path:
        fig.savefig(path, dpi=150)
    return fig


def plot_objective_alignment(df, k=None, path=None):
    """L'objectif optimisé prédit-il la protection réelle ? Un point par méthode, pour un k donné.

    A gauche : couverture des voisinages. A droite : contacts coupés. Si l'objectif est un bon proxy,
    les points descendent de gauche à droite (plus d'objectif = moins d'infectés).
    """
    k = df["k"].max() if k is None else k
    sub = df[df["k"] == k]  # une ligne par méthode, pour ce k seulement
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), sharey=True)
    panels = [("coverage_pct", "couverture des voisinages (% de la population)"),
              ("cut_pct", "contacts coupés (% du poids total des contacts)")]
    for ax, (col, label) in zip(axes, panels):
        for _, row in sub.iterrows():
            color, marker = STYLES.get(row["method"], (None, "o"))
            ax.scatter(row[col], row["attack_mean"], color=color, marker=marker, s=80)
        # corrélation de Pearson ; NaN si tous les x sont identiques
        r = np.corrcoef(sub[col], sub["attack_mean"])[0, 1] if sub[col].std() > 0 else float("nan")
        ax.margins(x=0.12, y=0.12)  # marge autour des points : place pour les étiquettes
        ax.set_xlabel(label)
        ax.set_title(f"corrélation avec le taux d'attaque : {r:.2f}", fontsize=10)
        ax.grid(alpha=0.3)
    axes[0].set_ylabel("taux d'attaque moyen (plus bas = mieux)")
    fig.suptitle(f"L'objectif optimisé est-il un bon proxy ? (k = {k})")
    fig.tight_layout()
    # étiquettes en dernier, une fois la mise en page figée
    for ax, (col, _) in zip(axes, panels):
        _label_points(ax, [(r[col], r["attack_mean"], r["method"]) for _, r in sub.iterrows()])
    if path:
        fig.savefig(path, dpi=150)
    return fig


def plot_time(df, path=None):
    """Temps de calcul de la sélection (échelle log) en fonction de k."""
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for method, sub in df.groupby("method"):
        color, marker = STYLES.get(method, (None, "o"))
        sub = sub.sort_values("k")
        ax.plot(sub["k"], sub["time_s"], marker=marker, color=color, label=method)
    # échelle logarithmique : les temps vont de quelques millisecondes (heuristiques)
    # à plusieurs secondes (ILP), ce qui serait illisible en échelle linéaire
    ax.set_yscale("log")
    ax.set_xlabel("k = nombre de personnes ciblées")
    ax.set_ylabel("temps de sélection (s, échelle log)")
    ax.set_title("Temps de calcul")
    ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5), fontsize=8)
    ax.grid(alpha=0.3, which="both")  # "both" : grille aussi sur les graduations secondaires du log
    fig.tight_layout()
    if path:
        fig.savefig(path, dpi=150, bbox_inches="tight")
    return fig


def plot_quality_vs_time(df, k: int, path=None):
    """Compromis qualité / temps pour un k donné : en bas à gauche = meilleur."""
    sub = df[df["k"] == k]  # on fixe k : un seul point par méthode
    fig, ax = plt.subplots(figsize=(7, 5))
    for _, row in sub.iterrows():
        color, marker = STYLES.get(row["method"], (None, "o"))
        ax.scatter(row["time_s"], row["attack_mean"], color=color, marker=marker, s=90)
    ax.set_xscale("log")  # temps en échelle log, comme pour plot_time
    ax.margins(x=0.15, y=0.12)
    ax.set_xlabel("temps de sélection (s, échelle log)")
    ax.set_ylabel("taux d'attaque moyen (plus bas = mieux)")
    ax.set_title(f"Qualité contre temps de calcul (k = {k})")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    _label_points(ax, [(r["time_s"], r["attack_mean"], r["method"]) for _, r in sub.iterrows()], fontsize=9)
    if path:
        fig.savefig(path, dpi=150)
    return fig


def plot_graph_selection(G: nx.Graph, selected, title="", path=None, seed=0):
    """Dessine le graphe : nœuds colorés par groupe, personnes ciblées en gros avec un contour rouge."""
    # Disposition des nœuds (algorithme à ressorts) ; seed fixe => dessin reproductible
    pos = nx.spring_layout(G, seed=seed)
    # liste triée des groupes présents ("?" si un nœud n'a pas d'attribut "group")
    groups = sorted({G.nodes[v].get("group", "?") for v in G.nodes})
    cmap = plt.get_cmap("tab10")  # palette de 10 couleurs distinctes
    # une couleur par groupe ; le modulo 10 recommence la palette s'il y a plus de 10 groupes
    color_of = {g: cmap(i % 10) for i, g in enumerate(groups)}
    selected = set(selected)  # ensemble : test d'appartenance rapide

    fig, ax = plt.subplots(figsize=(8, 6))
    # arêtes très transparentes (alpha=0.08) pour ne pas noyer les nœuds
    nx.draw_networkx_edges(G, pos, alpha=0.08, ax=ax)
    nx.draw_networkx_nodes(
        G, pos, ax=ax,
        node_color=[color_of[G.nodes[v].get("group", "?")] for v in G.nodes],  # couleur = groupe
        node_size=[260 if v in selected else 40 for v in G.nodes],  # ciblés : gros points
        edgecolors=["red" if v in selected else "none" for v in G.nodes],  # ciblés : contour rouge
        linewidths=2,  # épaisseur du contour
    )
    ax.set_title(title)
    ax.axis("off")  # pas d'axes : les coordonnées n'ont pas de sens ici
    fig.tight_layout()
    if path:
        fig.savefig(path, dpi=150)
    return fig
