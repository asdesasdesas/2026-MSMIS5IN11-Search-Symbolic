"""Graphiques pour le notebook et le rapport."""
from __future__ import annotations
from matplotlib.transforms import Bbox

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np


# dictionnaire de styles : une couleur et un marqueur par méthode, pour que les figures soient lisibles
# (une méthode garde la même apparence d'un graphique à l'autre)
STYLES = {  
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


# Décalages (en points) utilisés à tour de rôle pour que deux étiquettes voisines ne se chevauchent pas
# Positions d'étiquette essayées dans l'ordre : (décalage x, décalage y en points, alignement horizontal, vertical)

_CANDIDATES = [ #liste des positions possibles que la fonction _label_points() va tester pour chaque étiquette.
    (8, 6, "left", "bottom"), (8, -6, "left", "top"),
    (-8, 6, "right", "bottom"), (-8, -6, "right", "top"),
    (0, 10, "center", "bottom"), (0, -10, "center", "top"),
    (18, 20, "left", "bottom"), (18, -20, "left", "top"),
    (-18, 20, "right", "bottom"), (-18, -20, "right", "top"),
    (0, 28, "center", "bottom"), (0, -28, "center", "top"),
]


def _label_points(ax, points, fontsize=8): #Écrit le nom de chaque méthode près de son point, sans chevauchement

    # on commence par regrouper les méthodes qui tombent sur le même point
    groups = {} 
    for x, y, name in points:
        # avec round(..., 6), on considère que deux points quasi identiques (à 6 décimales près) sont considérés comme le même
        # setdefault(clé, []) renvoie la liste associée à la clé, et la crée vide si elle n'existe pas encore
        # on y ajoute ensuite le nom avec append
        groups.setdefault((round(float(x), 6), round(float(y), 6)), []).append(name)

    # puis on va mesurer le graphique tel qu'il sera dessiné
    fig = ax.figure       
    fig.canvas.draw()        # on force un premier dessin,s ans lui, les tailles et positions ne sont pas encore calculées
    renderer = fig.canvas.get_renderer()   # l'objet qui sait mesurer les éléments dessinés
    axbox = ax.get_window_extent(renderer) # rectangle occupé par les axes, en pixels
    keys = sorted(groups)    # liste triée des points : l'ordre de traitement est donc toujours le même
    pad = 7 * fig.dpi / 72   # marge autour d'un marqueur : 7 points convertis en pixels (1 point = 1/72 de pouce)

    # on regarde les zones déjà occupées : d'abord tous les marqueurs, puis les étiquettes posées

    # ax.transData.transform convertit les coordonnées des données (x, y) en coordonnées en pixels (px, py)
    # pour chaque point, on crée un petit rectangle (Bbox) centré dessus, de demi-côté pad
    taken = [Bbox([[px - pad, py - pad], [px + pad, py + pad]]) for px, py in ax.transData.transform(keys)]

    # on va placer une étiquette par point
    for key in keys:
        text = "\n".join(groups[key])  # plusieurs méthodes au même point : une par ligne dans la même étiquette
        best = None  # on regarde ala meilleure position trouvée pour l'instant
        for cand in _CANDIDATES:  # on essaie chaque position possible de l'étiquette
            dx, dy, ha, va = cand
            # on crée l'étiquette provisoirement pour mesurer sa taille à cet endroit

            # textcoords="offset points" : le décalage (dx, dy) est exprimé en points à partir du point (key)
            ann = ax.annotate(text, key, textcoords="offset points", xytext=(dx, dy),
                              fontsize=fontsize, ha=ha, va=va)
            
            box = ann.get_window_extent(renderer)  # rectangle occupé par ce texte, en pixels

            ann.remove()  # on retire l'étiquette d'essai

            # on va ensuite regardeer si le texte est entièrement à l'intérieur des axes 
            inside = (axbox.x0 <= box.x0 and box.x1 <= axbox.x1 and
                      axbox.y0 <= box.y0 and box.y1 <= axbox.y1)
            
            # score = nombre de zones déjà occupées que le texte recouvre (overlaps donne True/False, et sum compte les True)
            # + une pénalité de 100 si le texte sort des axes : un score plus bas est meilleur
            score = sum(box.overlaps(t) for t in taken) + (0 if inside else 100)
            if best is None or score < best[0]:
                best = (score, cand, box)  # nouvelle meilleure position
            if score == 0: #si ka position est parfaite( aucun chevauchement dans les axes), alors il est inutile d'essayer les autres
                break  

        # on récupère la meilleure position ; `_` ignore le score, qui ne sert plus
        # et (dx, dy, ha, va) est déballé directement à partir du candidat
        _, (dx, dy, ha, va), box = best

        # on dessine l'étiquette définitive à la meilleure position
        ax.annotate(text, key, textcoords="offset points", xytext=(dx, dy),
                    fontsize=fontsize, ha=ha, va=va)
        
        taken.append(box)  # cette zone devient occupée : les étiquettes suivantes l'éviteront
# Ces fonctions utilisent des éléments définis ailleurs dans plots.py :
#   plt (matplotlib.pyplot), np (numpy), nx (networkx), STYLES (couleur et marqueur de chaque méthode)
#   et _label_points (placement des étiquettes sans chevauchement)

def plot_attack_rate(df, baseline: float, path=None, title="Taux d'attaque selon la méthode"): #fraction de la population infectée en fonction de k
   
    fig, ax = plt.subplots(figsize=(7, 4.5))

    for method, sub in df.groupby("method"):  # une courbe par méthode : groupby sépare le tableau en un sous-tableau par méthode
        color, marker = STYLES.get(method, (None, "o"))  # style de la méthode récupérée dans SYTLES définie avant 
        sub = sub.sort_values("k")  # on trie par k pour que la ligne ne zigzague pas
        ax.plot(sub["k"], sub["attack_mean"], marker=marker, color=color, label=method)

    # ligne horizontale de référence : taux d'attaque sans aucune intervention
    ax.axhline(baseline, color="black", linestyle="--", label="sans intervention")
    ax.set_xlabel("k = nombre de personnes ciblées")  # 
    ax.set_ylabel("taux d'attaque moyen (SIR)")      
    ax.set_title(title)
    ax.legend(loc="lower left", fontsize=8)  
    ax.grid(alpha=0.3)  
    fig.tight_layout()  

    if path:  # on n'enregistre le fichier que si un chemin est fourni
        fig.savefig(path, dpi=150)  # dpi = résolution de l'image
    return fig 


def plot_major_outbreak(df, baseline_p: float, path=None): #Probabilité d'épidémie majeure (taux d'attaque >= seuil) en fonction de k
    
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for method, sub in df.groupby("method"): 
        color, marker = STYLES.get(method, (None, "o"))
        sub = sub.sort_values("k")
        ax.plot(sub["k"], sub["p_major"], marker=marker, color=color, label=method)

    # ligne de référence : la probabilité d'épidémie majeure sans intervention, pour comparaison
    ax.axhline(baseline_p, color="black", linestyle="--", label="sans intervention")
    ax.set_xlabel("k = nombre de personnes ciblées")
    ax.set_ylabel("probabilité d'épidémie majeure")
    ax.set_title("Probabilité qu'une épidémie démarre vraiment")
    ax.set_ylim(0, 1.02)  # axe borné : c'est une probabilité (la marge de 0.02 en haut améliore la lisibilité)
    ax.legend(loc="lower left", fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    if path:
        fig.savefig(path, dpi=150)
    return fig


def plot_objective_alignment(df, k=None, path=None): #on regarde si l'objectif optimisé prédit la protection réelle

    #A gauche : couverture des voisinage, a droite : contacts coupés; si l'objectif est un bon proxy,
    #les points descendent de gauche à droite : plus d'objectif = moins d'infectés
   
    k = df["k"].max() if k is None else k  # si aucun k n'est donné, on prend le plus grand k testé

    sub = df[df["k"] == k]  # une ligne par méthode, pour ce k seulement

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), sharey=True) #on créee 2 graphiques côtes à côtes
    # on regarde quel tritre, axes à mettres pour les 2 grpahes 
    panels = [("coverage_pct", "couverture des voisinages (% de la population)"),
              ("cut_pct", "contacts coupés (% du poids total des contacts)")]
    
    # zip associe chaque graphique (ax) à son couple (colonne, titre)
    for ax, (col, label) in zip(axes, panels):

        # iterrows parcourt les lignes du tableau : un point par méthode, avec x = valeur de l'objectif et y = taux d'attaque obtenu
        for _, row in sub.iterrows():
            color, marker = STYLES.get(row["method"], (None, "o"))
            ax.scatter(row[col], row["attack_mean"], color=color, marker=marker, s=80)  # s = taille du point

        # corrélation de Pearson entre l'objectif (x) et le taux d'attaque (y) ;
        # np.corrcoef renvoie une matrice 2x2 : [0, 1] est la corrélation entre les deux séries
        # NaN si tous les x sont identiques (écart-type nul), car elle n'est alors pas définie
        r = np.corrcoef(sub[col], sub["attack_mean"])[0, 1] if sub[col].std() > 0 else float("nan")

        ax.margins(x=0.12, y=0.12)
        ax.set_xlabel(label)
        ax.set_title(f"corrélation avec le taux d'attaque : {r:.2f}", fontsize=10)  # :.2f = 2 décimales
        ax.grid(alpha=0.3)

    axes[0].set_ylabel("taux d'attaque moyen (plus bas = mieux)")
    fig.suptitle(f"L'objectif optimisé est-il un bon proxy ? (k = {k})") 
    fig.tight_layout()

    
    for ax, (col, _) in zip(axes, panels): # (col, _) : on ne garde que la colonne, le titre de l'axe est ignoré ici
        _label_points(ax, [(r[col], r["attack_mean"], r["method"]) for _, r in sub.iterrows()])
        # chaque point est un triplet (x, y, nom de la méthode), le format attendu par _label_points
    if path:
        fig.savefig(path, dpi=150)
    return fig


def plot_time(df, path=None): #Temps de calcul de la sélection en fonction de k
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for method, sub in df.groupby("method"):
        color, marker = STYLES.get(method, (None, "o"))
        sub = sub.sort_values("k")
        ax.plot(sub["k"], sub["time_s"], marker=marker, color=color, label=method)
    # échelle logarithmique, c'est-à-dire que les temps vont de quelques millisecondes à plusieurs secondes (ILP)
    ax.set_yscale("log")
    ax.set_xlabel("k = nombre de personnes ciblées")
    ax.set_ylabel("temps de sélection (s, échelle log)")
    ax.set_title("Temps de calcul")
    ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5), fontsize=8)
    ax.grid(alpha=0.3, which="both")  # which="both" : grille aussi sur les graduations secondaires de l'échelle log
    fig.tight_layout()
    if path:
        # bbox_inches="tight" veut dire que l'image enregistrée est recadrée pour inclure tout ce qui est dessiné,
        # y compris la légende placée hors des axes sinon elle serait coupée
        fig.savefig(path, dpi=150, bbox_inches="tight")
    return fig


def plot_quality_vs_time(df, k: int, path=None): #Compromis qualité / temps pour un k donné : en bas à gauche = meilleur
    sub = df[df["k"] == k]  
    fig, ax = plt.subplots(figsize=(7, 5))
    for _, row in sub.iterrows():
        color, marker = STYLES.get(row["method"], (None, "o"))
        ax.scatter(row["time_s"], row["attack_mean"], color=color, marker=marker, s=90)
    ax.set_xscale("log")  # temps en échelle logarithmique, comme dans plot_time
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
    #Dessine le graphe : nœuds colorés par groupe, personnes ciblées en gros avec un contour rouge
    
    # disposition des nœuds par un algorithme à ressorts ; la graine fixe rend le dessin reproductible
    pos = nx.spring_layout(G, seed=seed)
    # liste triée des groupes présents ("?" si un nœud n'a pas d'attribut "group") ; les {} forment un ensemble (sans doublons)
    groups = sorted({G.nodes[v].get("group", "?") for v in G.nodes})
    cmap = plt.get_cmap("tab10")  # palette de 10 couleurs distinctes
    # une couleur par groupe ; le modulo 10 recommence la palette s'il y a plus de 10 groupes
    color_of = {g: cmap(i % 10) for i, g in enumerate(groups)}
    selected = set(selected)  # ensemble : test d'appartenance rapide

    fig, ax = plt.subplots(figsize=(8, 6))
   
    nx.draw_networkx_edges(G, pos, alpha=0.08, ax=ax) # arêtes très transparentes (alpha=0.08) 
    nx.draw_networkx_nodes(
        G, pos, ax=ax,
        node_color=[color_of[G.nodes[v].get("group", "?")] for v in G.nodes],  # couleur du nœud = couleur de son groupe
        node_size=[260 if v in selected else 40 for v in G.nodes],  # les personnes ciblées sont dessinées en gros
        edgecolors=["red" if v in selected else "none" for v in G.nodes],  # et entourées de rouge
        linewidths=2,  # épaisseur du contour
    )
    ax.set_title(title)
    ax.axis("off")  # pas d'axes, les coordonnées n'ont pas de sens ici
    fig.tight_layout()
    if path:
        fig.savefig(path, dpi=150)
    return fig