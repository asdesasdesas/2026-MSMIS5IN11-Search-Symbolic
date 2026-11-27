"""Tests ciblés sur les règles reprises des notebooks Dung et VAF."""

import unittest
import sys
from pathlib import Path

# Permet d’importer les modules du dossier src lors de unittest discover.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from argumentation import (
    AF,
    VAF,
    af_from_audience,
    defeats_under_audience,
    grounded,
    preferred,
    stable,
    is_admissible,
)

from verifier import grounded_verifier

from medical_case import (
    AUDIENCES,
    ATTACKS,
    ARGUMENT_TEXT,
    build_vaf,
)


class DungTests(unittest.TestCase):

    def test_single_attack_grounded(self):
        af = AF({"a", "b"}, {("a", "b")})
        self.assertEqual(
            grounded(af),
            frozenset({"a"})
        )

    def test_mutual_attack_preferred_and_no_stable_if_self_attack_present(self):
        af = AF(
            {"a", "b", "c", "d"},
            {("a", "b"), ("b", "a"), ("c", "c")}
        )

        # d est isolé et accepté dans toutes les extensions.
        self.assertEqual(
            grounded(af),
            frozenset({"d"})
        )

        self.assertEqual(
            set(preferred(af)),
            {
                frozenset({"a", "d"}),
                frozenset({"b", "d"})
            }
        )

        self.assertEqual(
            stable(af),
            []
        )

    def test_admissibility_requires_conflict_free_and_defence(self):
        af = AF(
            {"a", "b"},
            {("a", "b"), ("b", "a")}
        )

        self.assertTrue(
            is_admissible(af, {"a"})
        )

        self.assertFalse(
            is_admissible(af, {"a", "b"})
        )


class VAFTests(unittest.TestCase):

    def test_equal_values_do_not_block_attack(self):
        vaf = VAF(
            {"a", "b"},
            {("a", "b")},
            {"a": "v", "b": "v"}
        )

        self.assertTrue(
            defeats_under_audience(vaf, ["v"], "a", "b")
        )

        self.assertEqual(
            af_from_audience(vaf, ["v"]).attacks,
            {("a", "b")}
        )

    def test_less_preferred_attacker_is_blocked(self):

        vaf = VAF(
            {"a", "b"},
            {("a", "b")},
            {"a": "efficacite", "b": "qualite"}
        )

        audience = ["qualite", "efficacite"]

        self.assertFalse(
            defeats_under_audience(vaf, audience, "a", "b")
        )

        self.assertEqual(
            af_from_audience(vaf, audience).attacks,
            set()
        )

    def test_course_canonical_three_value_cycle(self):

        # Exemple canonique du notebook VAF.
        vaf = VAF(
            {"a", "b", "c"},
            {("a", "b"), ("b", "c"), ("c", "a")},
            {
                "a": "verite",
                "b": "confiance",
                "c": "solidarite",
            },
        )

        audiences = [
            (
                ["verite", "confiance", "solidarite"],
                {"a", "c"},
            ),
            (
                ["confiance", "solidarite", "verite"],
                {"a", "b"},
            ),
            (
                ["solidarite", "verite", "confiance"],
                {"b", "c"},
            ),
        ]

        for order, expected in audiences:
            self.assertEqual(
                grounded(af_from_audience(vaf, order)),
                frozenset(expected)
            )

    def test_invalid_audience_is_rejected(self):

        vaf = VAF(
            {"a", "b"},
            {("a", "b")},
            {"a": "efficacite", "b": "qualite"}
        )

        with self.assertRaises(ValueError):
            af_from_audience(vaf, ["efficacite"])

    def test_medical_case_keeps_same_initial_arguments_and_attacks(self):

        vaf = build_vaf()

        self.assertEqual(
            vaf.args,
            set(ARGUMENT_TEXT)
        )

        self.assertEqual(
            vaf.attacks,
            ATTACKS
        )

        filtered = {
            frozenset(
                af_from_audience(vaf, order).attacks
            )
            for order in AUDIENCES.values()
        }

        self.assertGreaterEqual(
            len(filtered),
            2
        )


class IndependentVerifierTests(unittest.TestCase):
    """
    Vérification indépendante de l'extension grounded.
    """

    def test_grounded_verifier_matches_grounded(self):

        af = AF(
            {"A", "B"},
            {("A", "B")}
        )

        self.assertEqual(
            grounded(af),
            grounded_verifier(af)
        )

    def test_medical_case_matches_verifier(self):

        af = AF(
            ARGUMENT_TEXT.keys(),
            ATTACKS
        )

        self.assertEqual(
            grounded(af),
            grounded_verifier(af)
        )


if __name__ == "__main__":
    unittest.main()
