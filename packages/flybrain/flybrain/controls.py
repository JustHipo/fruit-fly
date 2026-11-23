"""Controles de topologia: versiones degradadas del conectoma.

Diseno tomado de `eganeganegan/flydoom`. La idea es escalonada: si el resultado
real le gana a `shuffle_weights`, importan los pesos medidos; si le gana a
`degree_preserving` pero no a `shuffle_weights`, importa el cableado especifico
mas alla de los grados; si no le gana a `erdos_renyi`, solo importaban el tamano
y la densidad.

Ninguna de estas funciones modifica el conectoma original: todas devuelven uno
nuevo (CLAUDE.md, regla 3).
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np

from flybrain.data import Connectome


def shuffle_weights(conn: Connectome, seed: int = 0) -> Connectome:
    """Topologia intacta, pesos permutados entre aristas."""
    rng = np.random.default_rng(seed)
    return replace(conn, weight=rng.permutation(conn.weight))


def erdos_renyi_matched(conn: Connectome, seed: int = 0) -> Connectome:
    """Mismo N y E exactos, aristas completamente nuevas, pesos permutados."""
    rng = np.random.default_rng(seed)
    n, e = conn.n_neurons, conn.n_edges
    return replace(
        conn,
        src=rng.integers(0, n, e, dtype=np.int32),
        dst=rng.integers(0, n, e, dtype=np.int32),
        weight=rng.permutation(conn.weight),
    )


def degree_preserving_rewire(
    conn: Connectome, swaps_per_edge: int = 5, seed: int = 0
) -> Connectome:
    """Intercambios dobles de arista: cada nodo conserva su grado exacto.

    Toma dos aristas (a->b) y (c->d) y las convierte en (a->d) y (c->b). Eso
    mantiene el grado de salida de a y c y el de entrada de b y d, pero destruye
    el patron de conexion especifico.
    """
    rng = np.random.default_rng(seed)
    dst = conn.dst.copy()
    e = len(dst)
    for _ in range(swaps_per_edge * e // 2):
        i, j = rng.integers(0, e, 2)
        dst[i], dst[j] = dst[j], dst[i]
    return replace(conn, dst=dst)


CONTROLS = {
    "shuffle_weights": shuffle_weights,
    "degree_preserving": degree_preserving_rewire,
    "erdos_renyi": erdos_renyi_matched,
}
