"""
Vérificateur indépendant.

Cette implémentation recalcule l'extension grounded
sans utiliser la fonction grounded() du moteur principal.
L'objectif est de vérifier que les résultats obtenus
sont cohérents avec une seconde implémentation.
"""


def grounded_verifier(af):
    """
    Calcule indépendamment l'extension grounded.

    Méthode :
    - partir de l'ensemble vide ;
    - ajouter les arguments défendus ;
    - répéter jusqu'à stabilisation.
    """

    accepted = set()

    while True:

        new_accepted = set(accepted)

        for arg in af.args:

            attackers = af.attackers(arg)

            defended = True

            for attacker in attackers:

                if not any(
                    (defender, attacker) in af.attacks
                    for defender in accepted
                ):
                    defended = False
                    break

            if defended:
                new_accepted.add(arg)

        if new_accepted == accepted:
            return frozenset(accepted)

        accepted = new_accepted
