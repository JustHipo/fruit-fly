"""Subgrafo inducido: quedarse con un subconjunto de neuronas y TODAS las
aristas reales medidas entre ellas, sin inventar ni aproximar ninguna.

Generico y reusable (no especifico de patas ni de music-fly): cualquier
proyecto que necesite recortar el conectoma completo a un subconjunto para
correr en tiempo real puede usar esto.
"""

from __future__ import annotations

import numpy as np

from flybrain.data import Connectome


def induced_subgraph(conn: Connectome, indices: np.ndarray) -> Connectome:
    """Devuelve un Connectome nuevo con solo `indices` y sus aristas reales.

    Reindexa 0..len(indices)-1 en el mismo orden que `indices`. Una arista del
    original se retiene si y solo si tanto origen como destino quedaron
    seleccionados; nunca se agregan aristas que no estaban en el grafo medido.
    """
    indices = np.asarray(indices, dtype=np.int64)
    if len(np.unique(indices)) != len(indices):
        raise ValueError("indices no puede tener repetidos")

    n_full = conn.n_neurons
    remap = np.full(n_full, -1, dtype=np.int64)
    remap[indices] = np.arange(len(indices))

    keep = (remap[conn.src] >= 0) & (remap[conn.dst] >= 0)

    return Connectome(
        src=remap[conn.src[keep]].astype(np.int32),
        dst=remap[conn.dst[keep]].astype(np.int32),
        weight=conn.weight[keep].copy(),
        body_ids=conn.body_ids[indices].copy(),
        meta=conn.meta.iloc[indices].reset_index(drop=True),
    )
