"""Simulador del conectoma MaleCNS compartido por los dos proyectos.

El grafo medido nunca se modifica. Ver CLAUDE.md, regla 3.
"""

from flybrain.calibration import Baseline, PopulationReader, calibrate
from flybrain.controls import CONTROLS, degree_preserving_rewire, erdos_renyi_matched, shuffle_weights
from flybrain.data import Connectome, load_connectome, SIGN_STRICT
from flybrain.lif import LifNetwork, LifParams, LifState
from flybrain.populations import Populations
from flybrain.trace import Trace

__all__ = [
    "Baseline", "PopulationReader", "calibrate",
    "CONTROLS", "degree_preserving_rewire", "erdos_renyi_matched", "shuffle_weights",
    "Connectome", "load_connectome", "SIGN_STRICT",
    "LifNetwork", "LifParams", "LifState",
    "Populations",
    "Trace",
]
