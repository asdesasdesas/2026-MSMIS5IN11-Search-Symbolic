"""Point d'entrée : comparaison Dung / VAF sur un cas d'arthrose du genou."""

from argumentation import AF, af_from_audience, summarize

from medical_case import (
    ARGUMENT_TEXT,
    ARGUMENT_LABELS,
    ARGUMENT_POSITION,
    ATTACKS,
    AUDIENCES,
    AUDIENCE_DESCRIPTIONS,
    build_vaf,
)


def format_extensions(extensions):
    """Affichage stable des extensions."""
    return [
        "{" + ", ".join(sorted(extension)) + "}"
        for extension in extensions
    ]


def explain_grounded(extension):
    """
    Interprétation simple destinée à la soutenance.
    """

    chirurgie = []
    conservateur = []

    for arg in extension:
        if ARGUMENT_POSITION[arg] == "chirurgie":
            chirurgie.append(arg)
        else:
            conservateur.append(arg)

    return chirurgie, conservateur


def print_interpretation(extension):
    chirurgie, conservateur = explain_grounded(extension)

    print("\n  Interprétation clinique :")

    if len(chirurgie) > len(conservateur):
        print("  → Le modèle favorise plutôt la chirurgie.")
    elif len(conservateur) > len(chirurgie):
        print("  → Le modèle favorise plutôt le traitement conservateur.")
    else:
        print("  → Le modèle ne permet pas de départager clairement les options.")

    print("\n  Arguments retenus :")

    for arg in sorted(extension):
        print(f"     {arg} : {ARGUMENT_LABELS[arg]}")


def display_summary(label, af):
    """
    Affiche les sémantiques puis leur interprétation.
    """

    print(f"\n{label}")

    results = summarize(af)

    for semantics, extensions in results.items():
        print(f"  {semantics:12s}: {format_extensions(extensions)}")

    grounded_extension = results["grounded"][0]

    print_interpretation(grounded_extension)


if __name__ == "__main__":

    print("=" * 70)
    print("F2 — Argumentation à valeurs pour la décision médicale partagée")
    print("=" * 70)

    print("\nCas clinique : arthrose sévère du genou")
    print("Question : chirurgie ou traitement conservateur ?\n")

    print("Arguments du débat :\n")

    for arg_id, description in ARGUMENT_TEXT.items():
        print(f"{arg_id} : {description}")

    print("\nAttaques initiales :")
    print(sorted(ATTACKS))

    baseline = AF(ARGUMENT_TEXT.keys(), ATTACKS)

    display_summary(
        "1) Référence Dung — sans préférences de valeurs",
        baseline,
    )

    vaf = build_vaf()

    print("\n" + "=" * 70)
    print("Analyse avec les préférences des patients (VAF)")
    print("=" * 70)

    for label, audience in AUDIENCES.items():

        audience_af = af_from_audience(vaf, audience)

        print(f"\n\n2) {label}")

        print(f"  Profil : {AUDIENCE_DESCRIPTIONS[label]}")

        print(
            f"  Ordre de préférence : {' > '.join(audience)}"
        )

        print(
            f"  Attaques conservées : {sorted(audience_af.attacks)}"
        )

        display_summary(
            "  Résultats",
            audience_af,
        )
