"""Moteur Dung / VAF du projet F2.

Structure inspirée directement des notebooks du cours :
- Dung : AF, attackers, defeats, defends, conflict-free, admissible,
  grounded, preferred et stable.
- VAF : VAF, audience_rank, defeats_under_audience et af_from_audience.

Les fonctions sont volontairement proches des primitives pédagogiques du cours.
Le contenu médical est séparé dans medical_case.py.
"""

from itertools import chain, combinations


class AF:
    """Cadre abstrait de Dung : arguments + relation d'attaque.

    `args` contient des identifiants (A1, A2, ...).
    `attacks` contient des couples (attaquant, cible).
    """

    def __init__(self, args, attacks):
        self.args = set(args)
        self.attacks = set(attacks)

        # Vérification simple : une attaque ne peut relier que des arguments connus.
        unknown = {
            item for attack in self.attacks for item in attack
            if item not in self.args
        }
        if unknown:
            raise ValueError(f"Arguments inconnus dans les attaques : {unknown}")

    def attackers(self, x):
        """Renvoie les arguments qui attaquent directement x."""
        return {a for (a, b) in self.attacks if b == x}

    def __repr__(self):
        att = ", ".join(f"{a}->{b}" for (a, b) in sorted(self.attacks))
        return f"AF(args={sorted(self.args)}, attacks=[{att}])"


def is_conflict_free(af, S):
    """Vrai si aucun argument de S n'en attaque un autre dans S."""
    S = set(S)
    return not any(a in S and b in S for (a, b) in af.attacks)


def defeats(af, S, x):
    """Vrai si au moins un membre de S attaque x."""
    return any((a, x) in af.attacks for a in S)


def defends(af, S, x):
    """Vrai si S défait tous les attaquants de x."""
    return all(defeats(af, S, b) for b in af.attackers(x))


def is_admissible(af, S):
    """Un ensemble admissible est sans conflit et défend chacun de ses membres."""
    S = set(S)
    if not is_conflict_free(af, S):
        return False
    return all(defends(af, S, a) for a in S)


def powerset(iterable):
    """Énumère tous les sous-ensembles, du plus petit au plus grand."""
    items = list(iterable)
    return chain.from_iterable(
        combinations(items, r) for r in range(len(items) + 1)
    )


def grounded(af):
    """Extension grounded : point fixe obtenu depuis l'ensemble vide.

    À chaque itération, on ajoute les arguments défendus par l'ensemble courant.
    Le résultat est unique. C'est la sémantique prudente/sceptique présentée
    dans le notebook Dung.
    """
    S = set()
    while True:
        S_new = S | {x for x in af.args if defends(af, S, x)}
        if S_new == S:
            return frozenset(S)
        S = S_new


def preferred(af):
    """Extensions preferred : ensembles admissibles maximaux par inclusion.

    Plusieurs extensions peuvent exister et être incompatibles.
    """
    admissible = [
        frozenset(S) for S in powerset(af.args)
        if is_admissible(af, S)
    ]
    return [
        S for S in admissible
        if not any(S < other for other in admissible)
    ]


def stable(af):
    """Extensions stables : admissibles qui attaquent tout argument extérieur.

    Une AF peut ne posséder aucune extension stable.
    """
    result = []
    for candidate in powerset(af.args):
        S = set(candidate)
        if is_admissible(af, S) and all(
            defeats(af, S, x) for x in af.args if x not in S
        ):
            result.append(frozenset(S))
    return result


def range_of(af, S):
    """Portée S ∪ S+ : arguments retenus ou attaqués par S."""
    S = set(S)
    return S | {b for (a, b) in af.attacks if a in S}


def semi_stable(af):
    """Extensions admissibles qui maximisent la portée (semi-stable)."""
    admissible = [
        frozenset(S) for S in powerset(af.args)
        if is_admissible(af, S)
    ]
    best = max(len(range_of(af, S)) for S in admissible)
    return [S for S in admissible if len(range_of(af, S)) == best]


def ideal(af):
    """Plus grande extension admissible incluse dans toutes les preferred."""
    preferred_extensions = preferred(af)
    common = set.intersection(*(set(S) for S in preferred_extensions))
    candidates = [
        frozenset(S) for S in powerset(common)
        if is_admissible(af, S)
    ]
    return max(candidates, key=len)


def summarize(af):
    """Calcule les sémantiques Dung utilisées dans le projet."""
    return {
        "grounded": [grounded(af)],
        "preferred": preferred(af),
        "stable": stable(af),
        "semi-stable": semi_stable(af),
        "ideal": [ideal(af)],
    }


class VAF:
    """Value-based Argumentation Framework (Bench-Capon, 2003).

    `values` associe chaque argument à une valeur (fonction eta).
    `audience` est un ordre total, du plus préféré au moins préféré.
    """

    def __init__(self, args, attacks, values):
        self.args = set(args)
        self.attacks = set(attacks)
        self.values = dict(values)
        self.value_set = set(self.values.values())

        if set(self.values) != self.args:
            raise ValueError("Chaque argument doit être associé à exactement une valeur.")
        # Réutilise la validation de l'AF pour les extrémités des attaques.
        AF(self.args, self.attacks)

    def value_of(self, x):
        """Renvoie la valeur promue par l'argument x."""
        return self.values[x]

    def __repr__(self):
        vals = ", ".join(f"{a}:{v}" for a, v in sorted(self.values.items()))
        att = ", ".join(f"{a}->{b}" for a, b in sorted(self.attacks))
        return f"VAF(args={sorted(self.args)}, attacks=[{att}], values={{{vals}}})"


def audience_rank(audience, value):
    """Rang d'une valeur : 0 correspond à la valeur la plus préférée."""
    return audience.index(value)


def defeats_under_audience(vaf, audience, x, y):
    """L'attaque x->y réussit si eta(x) est au moins aussi préférée que eta(y).

    Le rang le plus petit correspond à la préférence la plus forte.
    L'égalité est donc acceptée, conformément à la règle du notebook.
    """
    if (x, y) not in vaf.attacks:
        return False
    return (
        audience_rank(audience, vaf.value_of(x))
        <= audience_rank(audience, vaf.value_of(y))
    )


def af_from_audience(vaf, audience):
    """Transforme un VAF en AF de Dung pour une audience donnée.

    On conserve uniquement les attaques qui réussissent sous cette audience.
    Les attaques bloquées ne sont pas transmises aux sémantiques de Dung.
    """
    if len(audience) != len(set(audience)) or set(audience) != vaf.value_set:
        raise ValueError("L'audience doit ordonner une fois chaque valeur du VAF.")

    surviving = {
        (x, y) for (x, y) in vaf.attacks
        if defeats_under_audience(vaf, audience, x, y)
    }
    return AF(vaf.args, surviving)
