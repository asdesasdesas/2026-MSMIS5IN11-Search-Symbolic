"""
Mesure simple des temps d'exécution.
"""

import random
import time

from argumentation import AF, summarize


def generate_random_af(n_arguments, n_attacks):

    args = {f"A{i}" for i in range(n_arguments)}

    attacks = set()

    arg_list = list(args)

    while len(attacks) < n_attacks:
        a = random.choice(arg_list)
        b = random.choice(arg_list)

        if a != b:
            attacks.add((a, b))

    return AF(args, attacks)


print("Benchmark")

for n in [4, 8, 12, 16]:

    af = generate_random_af(
        n_arguments=n,
        n_attacks=n * 2,
    )

    start = time.perf_counter()

    summarize(af)

    end = time.perf_counter()

    print(
        f"{n:2d} arguments : "
        f"{(end - start) * 1000:.3f} ms"
    )
