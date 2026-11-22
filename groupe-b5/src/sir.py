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
# Permet d’utiliser les annotations de types sans les évaluer immédiatement.
from __future__ import annotations

# dataclass crée automatiquement le constructeur de la classe Prepared.
from dataclasses import dataclass

# NetworkX sert à manipuler le graphe ; NumPy sert aux tableaux et aux tirages aléatoires.
import networkx as nx
import numpy as np

# On code chaque état par un entier pour stocker rapidement l’état de toutes les personnes.
S, I, R, IMMUNE = 0, 1, 2, 3


# ------------------------------------------------------------------------
# 1. PRÉPARATION DU GRAPHE POUR ACCÉLÉRER LES SIMULATIONS
# ------------------------------------------------------------------------
@dataclass
class Prepared:
    """Le graphe converti en listes d'adjacence d'entiers (beaucoup plus rapide à simuler)."""
    # Identifiants d’origine des personnes (ils ne sont pas forcément consécutifs).
    nodes: list
    # Dictionnaire : identifiant de la personne -> position dans les tableaux NumPy.
    index: dict
    adj: list  # adj[i] = tableau numpy des indices des voisins de i
    weights: list  # poids de contact des mêmes voisins, dans le même ordre
    mean_weight: float  # moyenne des poids des arêtes du graphe

    # Avec @property, on peut écrire p.n au lieu de p.n().
    @property
    def n(self) -> int:
        return len(self.nodes)


def prepare(G: nx.Graph) -> Prepared:
    # On trie les identifiants pour conserver un ordre stable entre les expériences.
    nodes = sorted(G.nodes)
    # Exemple : nodes = [12, 45, 80] donne index = {12: 0, 45: 1, 80: 2}.
    index = {v: i for i, v in enumerate(nodes)}
    # On vérifie tous les poids avant de lancer les simulations. d contient les attributs de l’arête.
    for _, _, d in G.edges(data=True):
        # Si aucun poids n’est indiqué, on utilise 1.0 par défaut.
        w = float(d.get("weight", 1.0))
        # On refuse les poids nuls, négatifs, infinis ou NaN.
        if not np.isfinite(w) or w <= 0:
            raise ValueError("les poids des contacts doivent être strictement positifs et finis")
    # Pour chaque personne, on stocke les indices de ses voisins dans un tableau.
    adj = [np.array([index[u] for u in G[v]], dtype=np.int64) for v in nodes]
    # On stocke les poids des mêmes contacts dans le même ordre que les voisins.
    weights = [np.array([float(G[v][u].get("weight", 1.0)) for u in G[v]], dtype=float)
               for v in nodes]
    # On récupère chaque poids une seule fois à partir des arêtes du graphe non orienté.
    all_weights = [float(d.get("weight", 1.0)) for _, _, d in G.edges(data=True)]
    # La moyenne sert à normaliser les poids. Sans arête, on utilise 1.0.
    mean_weight = float(np.mean(all_weights)) if all_weights else 1.0
    # On retourne toutes les informations nécessaires à la simulation.
    return Prepared(nodes, index, adj, weights, mean_weight)


# ------------------------------------------------------------------------
# 2. CALCUL DE LA TRANSMISSIBILITÉ ET DU R0 APPROXIMATIF (SIR UNIFORME)
# ------------------------------------------------------------------------
def transmissibility(beta: float, gamma: float) -> float:
    """Probabilité qu'un infecté contamine un voisin donné avant de guérir."""
    # Contrairement à beta, cette probabilité tient compte de toute la durée infectieuse.
    # Un infecté peut essayer de contaminer le même voisin pendant plusieurs tours.
    return beta / (beta + gamma - beta * gamma)


def estimate_r0(G: nx.Graph, beta: float, gamma: float) -> float:
    """R0 approximatif d'un SIR sur réseau : T * (<k^2> - <k>) / <k>.

    Sert à choisir beta et gamma : on veut un R0 > 1 (sinon pas d'épidémie à freiner),
    typiquement entre 2 et 4.
    """
    # k contient le degré de chaque personne, c’est-à-dire son nombre de voisins.
    # Ici, k ne désigne pas le budget de personnes à sélectionner.
    k = np.array([d for _, d in G.degree()], dtype=float)
    # Si le réseau non vide ne contient aucune arête, aucune transmission n’est possible.
    if k.mean() == 0:
        return 0.0
    # On multiplie la transmissibilité par l’excès de degré moyen.
    # Cette formule donne une approximation de R0, pas une mesure clinique exacte.
    return transmissibility(beta, gamma) * (np.mean(k**2) - k.mean()) / k.mean()


def beta_for_r0(G: nx.Graph, gamma: float, r0: float = 3.0) -> float:
    """Valeur de beta qui donne (à peu près) le R0 visé sur CE graphe.

    On inverse la formule de estimate_r0 : le réseau d'un hôpital (degré ~30) et celui
    d'une école n'ont pas le même beta critique, donc on calibre plutôt que de deviner.
    """
    # On récupère à nouveau le nombre de voisins de chaque personne.
    k = np.array([d for _, d in G.degree()], dtype=float)
    # q tient compte de la moyenne des degrés et de la moyenne de leurs carrés.
    q = (np.mean(k**2) - k.mean()) / k.mean()      # excès de degré moyen
    # On inverse R0 = T * q pour trouver la transmissibilité T souhaitée.
    t = r0 / q                                      # transmissibilité nécessaire
    # La transmissibilité recherchée doit être strictement comprise entre 0 et 1.
    if not 0 < t < 1:
        raise ValueError(f"R0={r0} impossible à atteindre sur ce graphe (transmissibilité {t:.2f})")
    # On inverse ensuite la formule de transmissibility pour obtenir beta.
    return t * gamma / (1 - t * (1 - gamma))


# ------------------------------------------------------------------------
# 3. SIMULATION D’UNE SEULE ÉPIDÉMIE
# p : graphe préparé ; removed_idx : indices des personnes immunisées.
# rng : générateur de nombres aléatoires ; n_seeds : nombre de candidats initiaux.
# transmission et seed_policy : choix du modèle et du mode d’infection initiale.
# ------------------------------------------------------------------------
def run_once(p: Prepared, removed_idx, beta: float, gamma: float, n_seeds: int,
             rng: np.random.Generator, transmission: str = "uniform",
             seed_policy: str = "resample") -> float:
    """Une simulation. Renvoie le taux d'attaque (fraction de la population infectée)."""
    # Vérification des paramètres : gamma et beta sont des probabilités ou paramètres bornés.
    if not 0 < gamma <= 1:
        raise ValueError("gamma doit être dans ]0, 1] (sinon l'épidémie ne finit jamais)")
    if not 0 <= beta <= 1:
        raise ValueError("beta doit être dans [0, 1]")
    # On accepte seulement les deux modèles de transmission prévus.
    if transmission not in ("uniform", "weighted"):
        raise ValueError("transmission doit valoir 'uniform' ou 'weighted'")
    # On accepte seulement les deux politiques de choix des cas initiaux.
    if seed_policy not in ("resample", "fixed"):
        raise ValueError("seed_policy doit valoir 'resample' ou 'fixed'")
    # Le nombre de candidats initiaux ne peut pas être négatif.
    if n_seeds < 0:
        raise ValueError("n_seeds doit être >= 0")
    # On ne demande pas plus de candidats initiaux que de personnes dans le graphe.
    n_seeds = min(n_seeds, p.n)

    # Toutes les personnes sont initialement susceptibles (S = 0).
    state = np.zeros(p.n, dtype=np.int8)
    # Les personnes sélectionnées passent à IMMUNE = 3 avant le début de l’épidémie.
    state[list(removed_idx)] = IMMUNE

    # On mélange les indices des personnes sans répétition.
    # Avec la même graine et le même graphe, cet ordre initial est reproductible.
    order = rng.permutation(p.n)                   # tirage commun à toutes les méthodes
    # fixed : les cas initiaux sont prélevés dans la population totale ; une cible
    # immunisée parmi les cas initiaux ne peut pas devenir infectée. Cela conserve
    # exactement les mêmes candidats initiaux entre stratégies, sans remplacement.
    # resample : comportement historique, un cas initial immunisé est remplacé.
    if seed_policy == "fixed":
        # On prend les n_seeds premiers candidats, puis on exclut les immunisés sans les remplacer.
        seeds = [i for i in order[:n_seeds] if state[i] != IMMUNE]
    else:
        # On exclut d’abord les immunisés, puis on prend jusqu’à n_seeds personnes.
        seeds = [i for i in order if state[i] != IMMUNE][:n_seeds]
    # Si aucun candidat ne peut être infecté, l’épidémie ne démarre pas.
    if not seeds:
        return 0.0
    # On rassemble les indices des cas initiaux dans un tableau NumPy.
    infected = np.array(seeds, dtype=np.int64)
    # Ces personnes passent à l’état infecté (I = 1).
    state[infected] = I

    # On répète les tours tant qu’il reste au moins une personne infectieuse.
    while infected.size:
        # Un ensemble évite de compter deux fois une personne contaminée par plusieurs voisins.
        newly = set()
        for i in infected:
            # On récupère les voisins de la personne infectée i.
            nb = p.adj[i]
            # On vérifie qu’elle a au moins un voisin.
            if nb.size:
                # On garde seulement les voisins susceptibles : ni infectés, ni guéris, ni immunisés.
                susceptible = nb[state[nb] == S]
                # On ne fait les tirages que s’il reste des voisins susceptibles.
                if susceptible.size:
                    # MODÈLE PONDÉRÉ : les contacts de poids différents ont des probabilités différentes.
                    if transmission == "weighted":
                        # même indexation que p.adj[i], pour garder les poids alignés.
                        # Le masque contient True pour chaque voisin susceptible et False sinon.
                        mask = (state[nb] == S)
                        # p_ij = 1 - exp(-beta * poids / poids moyen).
                        # np.expm1(x) calcule exp(x) - 1 avec une bonne précision numérique.
                        # Plus le poids est grand, plus la probabilité de transmission est élevée.
                        prob = -np.expm1(-beta * p.weights[i][mask] / p.mean_weight)
                        # On tire un nombre aléatoire entre 0 et 1 pour chaque voisin susceptible.
                        # Si ce nombre est inférieur à sa probabilité de transmission, il est contaminé.
                        hit = susceptible[rng.random(susceptible.size) < prob]
                    else:
                        # MODÈLE UNIFORME : même probabilité beta pour tous les voisins susceptibles.
                        hit = susceptible[rng.random(susceptible.size) < beta]
                    # On ajoute les personnes contaminées pendant ce tour, sans doublon.
                    newly.update(hit.tolist())
        # Après les transmissions, on tire une guérison pour chaque infecté du début du tour.
        recovers = rng.random(infected.size) < gamma
        # Les personnes qui guérissent passent à R = 2 et ne seront plus contaminées.
        state[infected[recovers]] = R
        # Le symbole ~ inverse le masque : on garde les personnes qui ne guérissent pas.
        still_infected = infected[~recovers]
        # On transforme l’ensemble des nouvelles contaminations en tableau NumPy.
        new_arr = np.fromiter(newly, dtype=np.int64, count=len(newly))
        # Les nouveaux contaminés passent à I à la fin du tour. Ils transmettront au tour suivant.
        state[new_arr] = I
        # La liste des infectés du tour suivant rassemble les anciens non guéris et les nouveaux.
        infected = np.concatenate([still_infected, new_arr])

    # Quand il ne reste plus d’infectés, toutes les personnes ayant été infectées sont dans R.
    # On divise leur nombre par la population totale, immunisés compris, pour comparer les méthodes.
    return float(np.count_nonzero(state == R)) / p.n


# ------------------------------------------------------------------------
# 4. CALCUL DES STATISTIQUES SUR PLUSIEURS SIMULATIONS
# ------------------------------------------------------------------------
def summarize(rates, major_threshold: float = 0.2) -> dict:
    """Résume un tableau de taux d'attaque.

    Les simulations se séparent en deux populations : celles où l'épidémie ne démarre pas
    (les cas initiaux guérissent avant de contaminer) et les vraies épidémies. La moyenne
    mélange les deux, d'où trois mesures complémentaires :
      - median       : taux d'attaque médian
      - p_major      : probabilité d'épidémie majeure (taux d'attaque >= major_threshold)
      - attack_major : taux d'attaque moyen parmi les épidémies majeures seulement
    """
    # On convertit les taux d’attaque en tableau NumPy pour faire les calculs.
    rates = np.asarray(rates, dtype=float)
    # Par défaut, une épidémie est dite majeure si au moins 20 % de la population est infectée.
    major = rates >= major_threshold
    return {
        # Moyenne des taux d’attaque, toutes simulations confondues.
        "mean": float(rates.mean()),
        # Écart-type empirique (ddof=1) : mesure de la dispersion ; 0 si une seule simulation.
        "std": float(rates.std(ddof=1)) if rates.size > 1 else 0.0,
        # Médiane : valeur centrale des taux d’attaque.
        "median": float(np.median(rates)),
        # Proportion des simulations classées comme épidémies majeures (True vaut 1).
        "p_major": float(major.mean()),
        # Moyenne uniquement des épidémies majeures ; NaN si aucune n’a eu lieu.
        "attack_major": float(rates[major].mean()) if major.any() else float("nan"),
        # On conserve aussi les taux individuels pour pouvoir les analyser ou les tracer.
        "rates": rates,
    }


# ------------------------------------------------------------------------
# 5. ÉVALUATION D’UNE SÉLECTION SUR PLUSIEURS ÉPIDÉMIES
# selected contient les identifiants des personnes choisies par une méthode de sélection.
# ------------------------------------------------------------------------
def evaluate(p: Prepared, selected, beta=0.02, gamma=0.2, n_runs=200, n_seeds=3,
             base_seed=0, major_threshold: float = 0.2, transmission: str = "uniform",
             seed_policy: str = "resample") -> dict:
    """Taux d'attaque sur n_runs simulations, avec la sélection vaccinée (voir summarize)."""
    # Il faut au moins une simulation pour calculer les statistiques.
    if n_runs < 1:
        raise ValueError("n_runs doit être >= 1")
    # Le seuil d’épidémie majeure est une proportion comprise entre 0 et 1.
    if not 0 <= major_threshold <= 1:
        raise ValueError("major_threshold doit être dans [0, 1]")
    # On convertit les identifiants sélectionnés en indices des tableaux du graphe préparé.
    removed = [p.index[v] for v in selected]
    # On réserve un tableau pour stocker le taux d’attaque de chaque simulation.
    rates = np.empty(n_runs)
    # On répète la simulation n_runs fois (200 par défaut).
    for r in range(n_runs):
        # Chaque répétition possède sa propre graine : base_seed + r.
        # Cela permet de reproduire les expériences et de partager l’ordre initial entre méthodes.
        # Les tirages suivants peuvent différer si les épidémies évoluent différemment.
        rng = np.random.default_rng(base_seed + r)
        # On lance une épidémie et on enregistre le taux d’attaque obtenu.
        rates[r] = run_once(p, removed, beta, gamma, n_seeds, rng, transmission, seed_policy)
    # On calcule les statistiques à partir de tous les taux d’attaque.
    return summarize(rates, major_threshold)


# ------------------------------------------------------------------------
# 6. CALIBRATION DE BETA POUR UN TAUX D’ATTAQUE CIBLE
# On cherche beta sans immunisation, avant de comparer les stratégies.
# Cette méthode fonctionne notamment avec le SIR pondéré.
# ------------------------------------------------------------------------
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
    # La cible est une proportion strictement comprise entre 0 et 1.
    if not 0 < target < 1:
        raise ValueError("target doit être strictement entre 0 et 1")
    # Il faut réaliser au moins une étape de dichotomie.
    if iterations < 1:
        raise ValueError("iterations doit être >= 1")
    # Fonction locale : pour un beta donné, elle estime le taux d’attaque moyen.
    def rate(b):
        # La liste vide [] signifie qu’aucune personne n’est immunisée.
        # On garde les mêmes graines et paramètres pendant la calibration.
        return evaluate(p, [], beta=b, gamma=gamma, n_runs=n_runs, n_seeds=n_seeds,
                        base_seed=base_seed, transmission=transmission,
                        seed_policy=seed_policy)["mean"]
    # On commence par les deux bornes possibles de beta : 0 et 1.
    lo, hi = 0.0, 1.0
    # On estime les taux d’attaque obtenus aux deux bornes.
    min_rate, max_rate = rate(lo), rate(hi)
    # Si la cible est hors de cet intervalle estimé, on signale qu’elle est inaccessible selon ce test.
    if target < min_rate or target > max_rate:
        # Retourne une borne, en expliquant que la cible est inaccessible.
        # On choisit la borne dont le taux d’attaque est le plus proche de la cible.
        beta = lo if abs(target - min_rate) <= abs(target - max_rate) else hi
        # On récupère le taux d’attaque correspondant à cette borne.
        actual = min_rate if beta == lo else max_rate
        return {"beta": beta, "attack": actual, "target": target, "reached": False}
    # On réduit progressivement l’intervalle de recherche par dichotomie.
    # La relation estimée par Monte-Carlo peut fluctuer : cette recherche reste approximative.
    for _ in range(iterations):
        # On teste la valeur située au milieu de l’intervalle.
        mid = (lo + hi) / 2
        # Si le taux estimé est trop faible, on recherche un beta plus grand.
        if rate(mid) < target:
            lo = mid
        else:
            # Sinon, on recherche un beta plus petit dans la moitié inférieure.
            hi = mid
    # Après les itérations, on retient le milieu du dernier intervalle.
    beta = (lo + hi) / 2
    # On mesure le taux d’attaque moyen correspondant au beta retenu.
    actual = rate(beta)
    # reached vaut True si l’écart absolu avec la cible est au plus 0.05 (5 points de pourcentage).
    return {"beta": beta, "attack": actual, "target": target,
            "reached": bool(abs(actual - target) <= 0.05)}
