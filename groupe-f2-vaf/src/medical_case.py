"""Scénario pédagogique : arthrose sévère du genou.

Ce projet illustre comment différentes priorités de valeurs
peuvent influencer une décision médicale partagée entre :

- une chirurgie (prothèse du genou),
- un traitement conservateur.

Les arguments et attaques représentent une modélisation simplifiée
du débat médical.

Ce programme est destiné à l'enseignement de l'argumentation
à valeurs (VAF) et ne constitue pas une aide médicale à la décision.
"""

from argumentation import VAF


# ------------------------------------------------------------------
# Arguments du débat
# ------------------------------------------------------------------

ARGUMENT_TEXT = {
    "A1": "La chirurgie améliore significativement la mobilité à long terme.",
    "A2": "La chirurgie comporte des risques de complications.",
    "A3": "Le traitement conservateur permet d'éviter les risques liés à la chirurgie.",
    "A4": "Le traitement conservateur peut être insuffisant pour retrouver une bonne mobilité.",
    "A5": "La chirurgie permet souvent une réduction plus importante et plus durable de la douleur.",
    "A6": "Le traitement conservateur permet souvent de contrôler la douleur sans chirurgie.",
}


# ------------------------------------------------------------------
# Interprétation des arguments
# Utilisée pour expliquer les résultats au public.
# ------------------------------------------------------------------

ARGUMENT_LABELS = {
    "A1": "Mobilité après chirurgie",
    "A2": "Risques chirurgicaux",
    "A3": "Éviter les risques chirurgicaux",
    "A4": "Limites du traitement conservateur",
    "A5": "Réduction de la douleur par chirurgie",
    "A6": "Contrôle de la douleur sans chirurgie",
}


# ------------------------------------------------------------------
# Position défendue par chaque argument
# Utilisé pour interpréter les extensions.
# ------------------------------------------------------------------

ARGUMENT_POSITION = {
    "A1": "chirurgie",
    "A2": "traitement_conservateur",
    "A3": "traitement_conservateur",
    "A4": "chirurgie",
    "A5": "chirurgie",
    "A6": "traitement_conservateur",
}


# ------------------------------------------------------------------
# Valeurs promues par les arguments
# ------------------------------------------------------------------

ARGUMENT_VALUES = {
    "A1": "mobilite",
    "A2": "securite",
    "A3": "securite",
    "A4": "mobilite",
    "A5": "qualite_de_vie",
    "A6": "qualite_de_vie",
}


# ------------------------------------------------------------------
# Attaques entre arguments
# ------------------------------------------------------------------

ATTACKS = {
    # Mobilité vs évitement de la chirurgie
    ("A1", "A3"),
    ("A3", "A1"),

    # Bénéfice attendu vs risques chirurgicaux
    ("A2", "A1"),
    ("A1", "A2"),

    # Limites du traitement conservateur
    ("A4", "A3"),

    # Deux visions du contrôle de la douleur
    ("A5", "A6"),
    ("A6", "A5"),

    # Une amélioration importante de la douleur
    # peut justifier certains risques opératoires
    ("A5", "A2"),
}


# ------------------------------------------------------------------
# Audiences (profils de patients)
# ------------------------------------------------------------------

AUDIENCES = {
    "Priorité à la mobilité": [
        "mobilite",
        "qualite_de_vie",
        "securite",
    ],

    "Priorité à la sécurité": [
        "securite",
        "qualite_de_vie",
        "mobilite",
    ],

    "Priorité à la qualité de vie": [
        "qualite_de_vie",
        "mobilite",
        "securite",
    ],
}


# ------------------------------------------------------------------
# Profils décrits en langage naturel
# ------------------------------------------------------------------

AUDIENCE_DESCRIPTIONS = {
    "Priorité à la mobilité":
        "Patient qui souhaite avant tout retrouver ses capacités physiques et son autonomie de déplacement.",

    "Priorité à la sécurité":
        "Patient qui veut avant tout éviter les risques et complications liés à une intervention chirurgicale.",

    "Priorité à la qualité de vie":
        "Patient qui privilégie principalement la réduction de la douleur et le confort au quotidien.",
}


def build_vaf():
    """Construit le VAF commun aux différentes audiences."""
    return VAF(
        args=ARGUMENT_TEXT.keys(),
        attacks=ATTACKS,
        values=ARGUMENT_VALUES,
    )
