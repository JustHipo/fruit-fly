"""Carga del conectoma MaleCNS como lista de aristas con signo.

Fuente: YijieYin/connectome_data_prep, matrices dispersas ya normalizadas.
Preferir las variantes `mcns_ad_*` (conectividad con separacion axon-dendrita),
biologicamente mas correctas que las planas.

Orientacion verificada contra los datos reales el 2026-09-14: en
`mcns_ad_inprop_all_neuron.npz` las COLUMNAS suman 1 (147.307 de 161.429), o sea
filas presinapticas y columnas postsinapticas, normalizado por input total del
postsinaptico.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
import scipy.sparse as sp

SignPolicy = Literal["dataset", "strict"]

# El dataset trae una columna `sign` ya calculada. Su criterio es colinergico
# positivo, GABA y glutamato negativos, y TODO lo demas positivo, incluida la
# histamina y las celulas sin clasificar.
#
# La politica "strict" corrige dos cosas frente a ese criterio:
#
#   histamina -> -1. En Drosophila la histamina es inhibitoria: abre canales de
#   cloruro (HisCl1 / ort) y es el transmisor de los fotorreceptores. Marcarla
#   excitatoria invierte el signo de 4.937 celulas, casi todas del lobulo optico.
#
#   ambiguos -> 0. Dopamina, octopamina y serotonina son moduladores, no
#   excitadores rapidos; `unclear` es directamente desconocido. Ponerlos en 0 es
#   declarar ignorancia en vez de adivinar (CLAUDE.md, regla 3).
SIGN_STRICT: dict[str, int] = {
    "acetylcholine": 1,
    "glutamate": -1,
    "gaba": -1,
    "histamine": -1,
    "dopamine": 0,
    "octopamine": 0,
    "serotonin": 0,
    "unclear": 0,
}

ID_COLUMN = "bodyid"
NT_COLUMN = "top_nt"


@dataclass(frozen=True)
class Connectome:
    """Grafo medido, inmutable. Aristas en formato COO."""

    src: np.ndarray          # (E,) indice presinaptico
    dst: np.ndarray          # (E,) indice postsinaptico
    weight: np.ndarray       # (E,) peso con signo aplicado
    body_ids: np.ndarray     # (N,) bodyid de MaleCNS por indice
    meta: pd.DataFrame       # (N, ...) tipo, clase, superclase, neurotransmisor

    @property
    def n_neurons(self) -> int:
        return len(self.body_ids)

    @property
    def n_edges(self) -> int:
        return len(self.src)

    def select(self, **criteria: object) -> np.ndarray:
        """Indices de las neuronas que cumplen todos los criterios.

        >>> conn.select(superclass="vnc_motor")
        >>> conn.select(superclass=["descending_neuron", "vnc_motor"])
        """
        mask = np.ones(self.n_neurons, dtype=bool)
        for column, value in criteria.items():
            if column not in self.meta.columns:
                raise KeyError(f"'{column}' no es una columna del metadata")
            values = value if isinstance(value, (list, tuple, set)) else [value]
            mask &= self.meta[column].isin(list(values)).to_numpy()
        return np.flatnonzero(mask)


def _signs(meta: pd.DataFrame, policy: SignPolicy) -> np.ndarray:
    if policy == "dataset":
        if "sign" not in meta.columns:
            raise ValueError("el metadata no trae columna 'sign'; usar policy='strict'")
        return meta["sign"].to_numpy(dtype=np.float32)

    nt = meta[NT_COLUMN].fillna("unclear").str.strip().str.lower()
    unmapped = set(nt.unique()) - set(SIGN_STRICT)
    if unmapped:
        raise ValueError(f"neurotransmisores no mapeados: {sorted(unmapped)}")
    return nt.map(SIGN_STRICT).to_numpy(dtype=np.float32)


def load_connectome(
    matrix_path: str | Path,
    meta_path: str | Path,
    sign_policy: SignPolicy = "strict",
    min_weight: float = 0.0,
) -> Connectome:
    """Carga la matriz dispersa y el metadata, y devuelve aristas con signo.

    `sign_policy` decide el criterio de signo; ver SIGN_STRICT para la diferencia.
    `min_weight` descarta aristas debiles. Por defecto entra el grafo completo,
    incluidas las aristas de contacto unico y las recurrentes.
    """
    matrix_path, meta_path = Path(matrix_path), Path(meta_path)
    for p in (matrix_path, meta_path):
        if not p.exists():
            raise FileNotFoundError(f"no existe {p}")

    matrix = sp.load_npz(matrix_path).tocoo()
    meta = pd.read_csv(meta_path, low_memory=False)

    if matrix.shape[0] != matrix.shape[1]:
        raise ValueError(f"la matriz no es cuadrada: {matrix.shape}")
    if matrix.shape[0] != len(meta):
        raise ValueError(
            f"matriz ({matrix.shape[0]}) y metadata ({len(meta)}) no coinciden"
        )
    if ID_COLUMN not in meta.columns:
        raise ValueError(f"falta la columna '{ID_COLUMN}' en el metadata")

    src, dst, value = matrix.row, matrix.col, matrix.data.astype(np.float32)

    if min_weight > 0.0:
        keep = value >= min_weight
        src, dst, value = src[keep], dst[keep], value[keep]

    weight = value * _signs(meta, sign_policy)[src]

    nonzero = weight != 0.0
    return Connectome(
        src=src[nonzero].astype(np.int32),
        dst=dst[nonzero].astype(np.int32),
        weight=weight[nonzero],
        body_ids=meta[ID_COLUMN].to_numpy(),
        meta=meta,
    )
