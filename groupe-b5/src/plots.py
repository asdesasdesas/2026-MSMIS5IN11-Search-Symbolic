"""Graphiques pour le notebook et le rapport."""
from __future__ import annotations

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np

STYLES = {  # une couleur / un marqueur par méthode, pour que les figures soient lisibles
    "random": ("tab:gray", "x"),
    "degree": ("tab:blue", "o"),
    "betweenness": ("tab:orange", "s"),
    "pagerank": ("tab:purple", "^"),
    "greedy": ("tab:green", "D"),
    "ilp": ("tab:red", "*"),
    "ilp_deg": ("tab:brown", "P"),
    "strength": ("tab:cyan", "v"),
    "greedy_edges": ("tab:olive", "d"),
    "ilp_edges": ("tab:pink", "h"),
}


def plot_attack_rate(df, baseline: float, path=None, title="Taux d'attaque selon la méthode"):
    """Taux d'attaque moyen (fraction de la population infectée) en fonction de k."""
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for method, sub in df.groupby("method"):
        color, marker = STYLES.get(method, (None, "o"))
        sub = sub.sort_values("k")
        ax.plot(sub["k"], sub["attack_mean"], marker=marker, color=color, label=method)
    ax.axhline(baseline, color="black", linestyle="--", label="sans intervention")
    ax.set_xlabel("k = nombre de personnes ciblées")
    ax.set_ylabel("taux d'attaque moyen (SIR)")
    ax.set_title(title)
    ax.legend(loc="lower left", fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    if path:
        fig.savefig(path, dpi=150)
    return fig


def plot_major_outbreak(df, baseline_p: float, path=None):
    """Probabilité d'épidémie majeure (taux d'attaque >= seuil) en fonction de k."""
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for method, sub in df.groupby("method"):
        color, marker = STYLES.get(method, (None, "o"))
        sub = sub.sort_values("k")
        ax.plot(sub["k"], sub["p_major"], marker=marker, color=color, label=method)
    ax.axhline(baseline_p, color="black", linestyle="--", label="sans intervention")
    ax.set_xlabel("k = nombre de personnes ciblées")
    ax.set_ylabel("probabilité d'épidémie majeure")
    ax.set_title("Probabilité qu'une épidémie démarre vraiment")
    ax.set_ylim(0, 1.02)
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
    sub = df[df["k"] == k]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), sharey=True)
    panels = [("coverage_pct", "couverture des voisinages (% de la population)"),
              ("cut_pct", "contacts coupés (% du poids total des contacts)")]
    for ax, (col, label) in zip(axes, panels):
        for _, row in sub.iterrows():
            color, marker = STYLES.get(row["method"], (None, "o"))
            ax.scatter(row[col], row["attack_mean"], color=color, marker=marker, s=80)
            ax.annotate(row["method"], (row[col], row["attack_mean"]),
                        textcoords="offset points", xytext=(5, 4), fontsize=8)
        r = np.corrcoef(sub[col], sub["attack_mean"])[0, 1] if sub[col].std() > 0 else float("nan")
        ax.set_xlabel(label)
        ax.set_title(f"corrélation avec le taux d'attaque : {r:.2f}", fontsize=10)
        ax.grid(alpha=0.3)
    axes[0].set_ylabel("taux d'attaque moyen (plus bas = mieux)")
    fig.suptitle(f"L'objectif optimisé est-il un bon proxy ? (k = {k})")
    fig.tight_layout()
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
    ax.set_yscale("log")
    ax.set_xlabel("k = nombre de personnes ciblées")
    ax.set_ylabel("temps de sélection (s, échelle log)")
    ax.set_title("Temps de calcul")
    ax.legend()
    ax.grid(alpha=0.3, which="both")
    fig.tight_layout()
    if path:
        fig.savefig(path, dpi=150)
    return fig


def plot_quality_vs_time(df, k: int, path=None):
    """Compromis qualité / temps pour un k donné : en bas à gauche = meilleur."""
    sub = df[df["k"] == k]
    fig, ax = plt.subplots(figsize=(6, 4.5))
    for _, row in sub.iterrows():
        color, marker = STYLES.get(row["method"], (None, "o"))
        ax.scatter(row["time_s"], row["attack_mean"], color=color, marker=marker, s=90)
        ax.annotate(row["method"], (row["time_s"], row["attack_mean"]),
                    textcoords="offset points", xytext=(6, 4))
    ax.set_xscale("log")
    ax.set_xlabel("temps de sélection (s, échelle log)")
    ax.set_ylabel("taux d'attaque moyen (plus bas = mieux)")
    ax.set_title(f"Qualité contre temps de calcul (k = {k})")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    if path:
        fig.savefig(path, dpi=150)
    return fig


def plot_graph_selection(G: nx.Graph, selected, title="", path=None, seed=0):
    """Dessine le graphe : nœuds colorés par groupe, personnes ciblées en gros avec un contour rouge."""
    pos = nx.spring_layout(G, seed=seed)
    groups = sorted({G.nodes[v].get("group", "?") for v in G.nodes})
    cmap = plt.get_cmap("tab10")
    color_of = {g: cmap(i % 10) for i, g in enumerate(groups)}
    selected = set(selected)

    fig, ax = plt.subplots(figsize=(8, 6))
    nx.draw_networkx_edges(G, pos, alpha=0.08, ax=ax)
    nx.draw_networkx_nodes(
        G, pos, ax=ax,
        node_color=[color_of[G.nodes[v].get("group", "?")] for v in G.nodes],
        node_size=[260 if v in selected else 40 for v in G.nodes],
        edgecolors=["red" if v in selected else "none" for v in G.nodes],
        linewidths=2,
    )
    ax.set_title(title)
    ax.axis("off")
    fig.tight_layout()
    if path:
        fig.savefig(path, dpi=150)
    return fig
