"""Simulation SIR sur un graphe de contacts (outil d'ÉVALUATION des sélections).

Modèle en temps discret. A chaque pas de temps :
  1. chaque infecté (I) contamine chacun de ses voisins sains (S) avec probabilité beta ;
  2. ensuite chaque infecté guérit (-> R) avec probabilité gamma.
Les personnes ciblées (testées / vaccinées) sont IMMUNISÉES : elles ne sont jamais
infectées et ne transmettent rien, comme si on les retirait du graphe.

Mesure : taux d'attaque = (nombre de personnes qui ont été infectées) / (population totale).
Le dénominateur est toujours n, pour que toutes les méthodes soient comparables.

Comparaison équitable : pour la simulation numéro r, tous les choix de k personnes
utilisent la même graine (base_seed + r) et le même ordre de tirage des cas initiaux.
"""
from __future__ import annotations

from dataclasses import dataclass

import networkx as nx
import numpy as np

S, I, R, IMMUNE = 0, 1, 2, 3


@dataclass
class Prepared:
    """Le graphe converti en listes d'adjacence d'entiers (beaucoup plus rapide à simuler)."""
    nodes: list
    index: dict
    adj: list  # adj[i] = tableau numpy des indices des voisins de i
    weights: list  # poids de contact des mêmes voisins, dans le même ordre
    mean_weight: float  # moyenne des poids des arêtes du graphe

    @property
    def n(self) -> int:
        return len(self.nodes)


def prepare(G: nx.Graph) -> Prepared:
    nodes = sorted(G.nodes)
    index = {v: i for i, v in enumerate(nodes)}
    for _, _, d in G.edges(data=True):
        w = float(d.get("weight", 1.0))
        if not np.isfinite(w) or w <= 0:
            raise ValueError("les poids des contacts doivent être strictement positifs et finis")
    adj = [np.array([index[u] for u in G[v]], dtype=np.int64) for v in nodes]
    weights = [np.array([float(G[v][u].get("weight", 1.0)) for u in G[v]], dtype=float)
               for v in nodes]
    all_weights = [float(d.get("weight", 1.0)) for _, _, d in G.edges(data=True)]
    mean_weight = float(np.mean(all_weights)) if all_weights else 1.0
    return Prepared(nodes, index, adj, weights, mean_weight)


def transmissibility(beta: float, gamma: float) -> float:
    """Probabilité qu'un infecté contamine un voisin donné avant de guérir."""
    return beta / (beta + gamma - beta * gamma)


def estimate_r0(G: nx.Graph, beta: float, gamma: float) -> float:
    """R0 approximatif d'un SIR sur réseau : T * (<k^2> - <k>) / <k>.

    Sert à choisir beta et gamma : on veut un R0 > 1 (sinon pas d'épidémie à freiner),
    typiquement entre 2 et 4.
    """
    k = np.array([d for _, d in G.degree()], dtype=float)
    if k.mean() == 0:
        return 0.0
    return transmissibility(beta, gamma) * (np.mean(k**2) - k.mean()) / k.mean()


def beta_for_r0(G: nx.Graph, gamma: float, r0: float = 3.0) -> float:
    """Valeur de beta qui donne (à peu près) le R0 visé sur CE graphe.

    On inverse la formule de estimate_r0 : le réseau d'un hôpital (degré ~30) et celui
    d'une école n'ont pas le même beta critique, donc on calibre plutôt que de deviner.
    """
    k = np.array([d for _, d in G.degree()], dtype=float)
    q = (np.mean(k**2) - k.mean()) / k.mean()      # excès de degré moyen
    t = r0 / q                                      # transmissibilité nécessaire
    if not 0 < t < 1:
        raise ValueError(f"R0={r0} impossible à atteindre sur ce graphe (transmissibilité {t:.2f})")
    return t * gamma / (1 - t * (1 - gamma))


def run_once(p: Prepared, removed_idx, beta: float, gamma: float, n_seeds: int,
             rng: np.random.Generator, transmission: str = "uniform",
             seed_policy: str = "resample") -> float:
    """Une simulation. Renvoie le taux d'attaque (fraction de la population infectée)."""
    if not 0 < gamma <= 1:
        raise ValueError("gamma doit être dans ]0, 1] (sinon l'épidémie ne finit jamais)")
    if not 0 <= beta <= 1:
        raise ValueError("beta doit être dans [0, 1]")
    if transmission not in ("uniform", "weighted"):
        raise ValueError("transmission doit valoir 'uniform' ou 'weighted'")
    if seed_policy not in ("resample", "fixed"):
        raise ValueError("seed_policy doit valoir 'resample' ou 'fixed'")
    if n_seeds < 0:
        raise ValueError("n_seeds doit être >= 0")
    n_seeds = min(n_seeds, p.n)

    state = np.zeros(p.n, dtype=np.int8)
    state[list(removed_idx)] = IMMUNE

    order = rng.permutation(p.n)                   # tirage commun à toutes les méthodes
    # fixed : les cas initiaux sont prélevés dans la population totale ; une cible
    # immunisée parmi les cas initiaux ne peut pas devenir infectée. Cela conserve
    # exactement les mêmes candidats initiaux entre stratégies, sans remplacement.
    # resample : comportement historique, un cas initial immunisé est remplacé.
    if seed_policy == "fixed":
        seeds = [i for i in order[:n_seeds] if state[i] != IMMUNE]
    else:
        seeds = [i for i in order if state[i] != IMMUNE][:n_seeds]
    if not seeds:
        return 0.0
    infected = np.array(seeds, dtype=np.int64)
    state[infected] = I

    while infected.size:
        newly = set()
        for i in infected:
            nb = p.adj[i]
            if nb.size:
                susceptible = nb[state[nb] == S]
                if susceptible.size:
                    if transmission == "weighted":
                        # même indexation que p.adj[i], pour garder les poids alignés.
                        mask = (state[nb] == S)
                        prob = -np.expm1(-beta * p.weights[i][mask] / p.mean_weight)
                        hit = susceptible[rng.random(susceptible.size) < prob]
                    else:
                        hit = susceptible[rng.random(susceptible.size) < beta]
                    newly.update(hit.tolist())
        recovers = rng.random(infected.size) < gamma
        state[infected[recovers]] = R
        still_infected = infected[~recovers]
        new_arr = np.fromiter(newly, dtype=np.int64, count=len(newly))
        state[new_arr] = I
        infected = np.concatenate([still_infected, new_arr])

    return float(np.count_nonzero(state == R)) / p.n


def summarize(rates, major_threshold: float = 0.2) -> dict:
    """Résume un tableau de taux d'attaque.

    Les simulations se séparent en deux populations : celles où l'épidémie ne démarre pas
    (les cas initiaux guérissent avant de contaminer) et les vraies épidémies. La moyenne
    mélange les deux, d'où trois mesures complémentaires :
      - median       : taux d'attaque médian
      - p_major      : probabilité d'épidémie majeure (taux d'attaque >= major_threshold)
      - attack_major : taux d'attaque moyen parmi les épidémies majeures seulement
    """
    rates = np.asarray(rates, dtype=float)
    major = rates >= major_threshold
    return {
        "mean": float(rates.mean()),
        "std": float(rates.std(ddof=1)) if rates.size > 1 else 0.0,
        "median": float(np.median(rates)),
        "p_major": float(major.mean()),
        "attack_major": float(rates[major].mean()) if major.any() else float("nan"),
        "rates": rates,
    }


def evaluate(p: Prepared, selected, beta=0.02, gamma=0.2, n_runs=200, n_seeds=3,
             base_seed=0, major_threshold: float = 0.2, transmission: str = "uniform",
             seed_policy: str = "resample") -> dict:
    """Taux d'attaque sur n_runs simulations, avec la sélection vaccinée (voir summarize)."""
    if n_runs < 1:
        raise ValueError("n_runs doit être >= 1")
    if not 0 <= major_threshold <= 1:
        raise ValueError("major_threshold doit être dans [0, 1]")
    removed = [p.index[v] for v in selected]
    rates = np.empty(n_runs)
    for r in range(n_runs):
        rng = np.random.default_rng(base_seed + r)
        rates[r] = run_once(p, removed, beta, gamma, n_seeds, rng, transmission, seed_policy)
    return summarize(rates, major_threshold)


def calibrate_beta_for_attack(p: Prepared, target: float = 0.65, gamma: float = 0.2,
                              n_seeds: int = 3, n_runs: int = 80, base_seed: int = 999,
                              transmission: str = "weighted", seed_policy: str = "fixed",
                              iterations: int = 12) -> dict:
    """Calibration par dichotomie sur le taux d'attaque *sans intervention*.

    Contrairement à une calibration à R0, ceci fonctionne avec des transmissions
    pondérées, MAIS la cible peut être irréalisable (petites composantes). On
    renvoie l'écart réel et le drapeau `reached` sans prétendre atteindre la cible.
    La calibration dépend de l'échantillonnage Monte-Carlo fixé : c'est un proxy.
    """
    if not 0 < target < 1:
        raise ValueError("target doit être strictement entre 0 et 1")
    if iterations < 1:
        raise ValueError("iterations doit être >= 1")
    def rate(b):
        return evaluate(p, [], beta=b, gamma=gamma, n_runs=n_runs, n_seeds=n_seeds,
                        base_seed=base_seed, transmission=transmission,
                        seed_policy=seed_policy)["mean"]
    lo, hi = 0.0, 1.0
    min_rate, max_rate = rate(lo), rate(hi)
    if target < min_rate or target > max_rate:
        # Retourne une borne, en expliquant que la cible est inaccessible.
        beta = lo if abs(target - min_rate) <= abs(target - max_rate) else hi
        actual = min_rate if beta == lo else max_rate
        return {"beta": beta, "attack": actual, "target": target, "reached": False}
    for _ in range(iterations):
        mid = (lo + hi) / 2
        if rate(mid) < target:
            lo = mid
        else:
            hi = mid
    beta = (lo + hi) / 2
    actual = rate(beta)
    return {"beta": beta, "attack": actual, "target": target,
            "reached": bool(abs(actual - target) <= 0.05)}
