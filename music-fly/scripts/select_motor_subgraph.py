"""Selecciona el subgrafo motor de pata, metodo de ARQUITECTURA.md 4.2.

Metodo anatomico y determinista (mismo principio que flyjump, adaptado de
via visual a via motora): las celulas se eligen por conectividad MEDIDA,
nunca porque "funcionen bien". Tres pasos:

  1. Motoneuronas de pata: superclass=vnc_motor, somaNeuromere en T1/T2/T3
     (patas delantera/media/trasera). Verificado contra el metadata real:
     491 celulas (171 T1, 174 T2, 146 T3).
  2. Premotoras: las celulas que mas sinapsis reales hacen sobre el paso 1,
     rankeadas por peso sinaptico total (|peso|, no firmado: una neurona
     inhibitoria fuerte es tan "premotora" como una excitatoria fuerte).
  3. Descendentes: mismo ranking, un salto mas atras desde las premotoras.

Se retienen TODAS las aristas reales entre el conjunto final (recurrentes y
de contacto unico incluidas), nunca aristas inventadas.

Uso:
    source .venv-brain/bin/activate
    python music-fly/scripts/select_motor_subgraph.py --n-premotor 2000 --n-descending 2000
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import scipy.sparse as sp

from flybrain.data import load_connectome
from flybrain.subgraph import induced_subgraph

REPO = Path(__file__).resolve().parents[2]
MATRIX = REPO / "data/connectome_data_prep/data/maleCNS/mcns_ad_inprop_all_neuron.npz"
META = REPO / "data/connectome_data_prep/data/maleCNS/mcns_all_neuron_meta.csv"
OUT_DIR = REPO / "out/music-fly/f1"


def top_upstream(conn, target_idx: np.ndarray, already: np.ndarray, n: int) -> np.ndarray:
    """Las `n` neuronas (fuera de `already`) que mas |peso sinaptico| aportan
    hacia `target_idx`, sumado por neurona fuente."""
    target_mask = np.zeros(conn.n_neurons, dtype=bool)
    target_mask[target_idx] = True

    hits = target_mask[conn.dst]
    src_hits = conn.src[hits]
    w_hits = np.abs(conn.weight[hits])

    totals = np.zeros(conn.n_neurons, dtype=np.float64)
    np.add.at(totals, src_hits, w_hits)

    already_mask = np.zeros(conn.n_neurons, dtype=bool)
    already_mask[already] = True
    totals[already_mask] = -1.0  # nunca re-seleccionar lo que ya esta

    order = np.argsort(totals)[::-1]
    order = order[totals[order] > 0]  # descartar quienes no aportan nada real
    return order[:n]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-premotor", type=int, default=2000)
    ap.add_argument("--n-descending", type=int, default=2000)
    args = ap.parse_args()

    print(f"Cargando conectoma completo desde {MATRIX.name}...")
    conn = load_connectome(MATRIX, META, sign_policy="strict")
    print(f"  {conn.n_neurons} neuronas, {conn.n_edges} aristas con signo no nulo")

    motor_idx = conn.select(superclass="vnc_motor", somaNeuromere=["T1", "T2", "T3"])
    print(f"\nPaso 1, motoneuronas de pata (T1/T2/T3): {len(motor_idx)}")
    by_neuromere = conn.meta.iloc[motor_idx]["somaNeuromere"].value_counts()
    print(f"  {dict(by_neuromere)}")

    premotor_idx = top_upstream(conn, motor_idx, motor_idx, args.n_premotor)
    print(f"\nPaso 2, premotoras (top {args.n_premotor} por peso sinaptico): {len(premotor_idx)}")

    selected_so_far = np.concatenate([motor_idx, premotor_idx])
    descending_idx = top_upstream(conn, premotor_idx, selected_so_far, args.n_descending)
    print(f"\nPaso 3, descendentes (top {args.n_descending}): {len(descending_idx)}")

    final_idx = np.unique(np.concatenate([motor_idx, premotor_idx, descending_idx]))
    print(f"\nSubgrafo final: {len(final_idx)} neuronas")
    print("  Objetivo del documento: 1.000 a 6.000")

    sub = induced_subgraph(conn, final_idx)
    print(f"  Aristas retenidas dentro del subgrafo: {sub.n_edges}")

    superclass_counts = sub.meta["superclass"].value_counts()
    print(f"\nComposicion por superclase:\n{superclass_counts}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    matrix_out = sp.coo_matrix(
        (sub.weight, (sub.src, sub.dst)), shape=(sub.n_neurons, sub.n_neurons)
    )
    sp.save_npz(OUT_DIR / "motor_subgraph.npz", matrix_out.tocsr())
    sub.meta.to_csv(OUT_DIR / "motor_subgraph_meta.csv", index=False)
    np.save(OUT_DIR / "motor_subgraph_body_ids.npy", sub.body_ids)
    print(f"\nGuardado en {OUT_DIR}/")


if __name__ == "__main__":
    main()
