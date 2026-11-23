"""Simulador leaky integrate-and-fire sobre el conectoma medido.

Parametros tomados de Shiu et al., derivados a su vez de Kakaria y de Bivort.

La implementacion usa gather mas `index_add_` sobre una lista de aristas,
recorrida por chunks. Deliberadamente NO usa matriz densa N*N (seria 110 GB a
165k neuronas) ni tensores sparse de PyTorch: la cobertura de kernels sparse en
MPS es pobre y falla o va lentisimo.

El estado se muta en el lugar dentro del paso, que es lo idiomatico y necesario
en computo numerico; la API de afuera es funcional (estado entra, estado sale).
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np
import torch

from flybrain.data import Connectome


@dataclass(frozen=True)
class LifParams:
    tau_m: float = 20.0          # ms, constante de membrana
    v_rest: float = -52.0        # mV
    v_thresh: float = -45.0      # mV
    v_reset: float = -52.0       # mV
    t_refract: float = 2.2       # ms
    inhib_delay: float = 4.0     # ms, retardo de la inhibicion
    weight_scale: float = 65.0   # mV por unidad de peso normalizado, ver nota
    dt: float = 1.0              # ms

    # weight_scale calibrado el 2026-09-14 con scripts/calibrate_scale.py. Por
    # debajo de 25 la actividad la domina el ruido inyectado y el conectoma real
    # es indistinguible de uno aleatorio (correlacion 0,997 a escala 5). Por
    # encima de 100 las tasas se van a 15 Hz o mas, poco plausible. A 65 la
    # correlacion contra el nulo es 0,21 y la tasa media 3,3 Hz.
    # PENDIENTE: validar contra registros reales, no solo contra el nulo.

    def __post_init__(self) -> None:
        if self.dt <= 0 or self.tau_m <= 0:
            raise ValueError("dt y tau_m deben ser positivos")
        if self.v_thresh <= self.v_rest:
            raise ValueError("el umbral debe estar por encima del reposo")


@dataclass
class LifState:
    v: torch.Tensor           # (N,) potencial de membrana
    refract: torch.Tensor     # (N,) ms restantes de refractario
    delayed: torch.Tensor     # (D, N) buffer circular de corriente inhibitoria
    cursor: int = 0           # posicion actual en el buffer circular


class LifNetwork:
    """Red LIF con la topologia del conectoma congelada."""

    def __init__(
        self,
        connectome: Connectome,
        params: LifParams | None = None,
        device: str = "mps",
        chunk_size: int = 1_000_000,
    ) -> None:
        self.params = params or LifParams()
        self.n = connectome.n_neurons
        self.chunk_size = chunk_size
        self.device = torch.device(device)

        src = torch.from_numpy(connectome.src.astype(np.int64))
        dst = torch.from_numpy(connectome.dst.astype(np.int64))
        w = torch.from_numpy(connectome.weight.astype(np.float32))

        # Excitatorias llegan en el acto; inhibitorias con retardo. Las de signo
        # cero (neurotransmisor sin asignar) no aportan corriente y se descartan.
        exc, inh = w > 0, w < 0
        self.exc_src, self.exc_dst = src[exc].to(self.device), dst[exc].to(self.device)
        self.exc_w = (w[exc] * self.params.weight_scale).to(self.device)
        self.inh_src, self.inh_dst = src[inh].to(self.device), dst[inh].to(self.device)
        self.inh_w = (w[inh] * self.params.weight_scale).to(self.device)

        self.delay_steps = max(1, int(round(self.params.inhib_delay / self.params.dt)))
        self.n_dropped = int((~exc & ~inh).sum())

    def initial_state(self) -> LifState:
        p = self.params
        return LifState(
            v=torch.full((self.n,), p.v_rest, device=self.device),
            refract=torch.zeros(self.n, device=self.device),
            delayed=torch.zeros(self.delay_steps, self.n, device=self.device),
        )

    def _accumulate(self, into, fired, src, dst, w) -> None:
        """Suma la corriente de las aristas cuya fuente disparo, por chunks."""
        for lo in range(0, src.numel(), self.chunk_size):
            hi = lo + self.chunk_size
            s, d, ww = src[lo:hi], dst[lo:hi], w[lo:hi]
            active = fired[s]
            if active.any():
                into.index_add_(0, d[active], ww[active])

    def step(
        self,
        state: LifState,
        external: torch.Tensor | None = None,
    ) -> tuple[LifState, torch.Tensor]:
        """Avanza un paso de `dt` ms. Devuelve el estado y quienes dispararon."""
        p = self.params

        fired = state.v >= p.v_thresh
        state.v = torch.where(fired, torch.full_like(state.v, p.v_reset), state.v)
        state.refract = torch.where(
            fired, torch.full_like(state.refract, p.t_refract), state.refract
        )

        current = state.delayed[state.cursor].clone()
        state.delayed[state.cursor].zero_()

        self._accumulate(current, fired, self.exc_src, self.exc_dst, self.exc_w)

        future = (state.cursor + self.delay_steps - 1) % self.delay_steps
        self._accumulate(state.delayed[future], fired, self.inh_src, self.inh_dst, self.inh_w)

        if external is not None:
            current = current + external

        leak = (p.v_rest - state.v) / p.tau_m
        integrating = state.refract <= 0
        state.v = state.v + p.dt * torch.where(integrating, leak + current, leak)
        state.refract = (state.refract - p.dt).clamp(min=0.0)
        state.cursor = (state.cursor + 1) % self.delay_steps

        return state, fired

    def noise(self, n_kicks: int = 300, amplitude: float = 8.0) -> torch.Tensor:
        """Corriente de fondo dispersa.

        Sin entrada el conectoma queda en silencio, asi que necesita ruido basal.
        Tecnica de `infinite-sugar`: pocos empujones fuertes y dispersos por ms,
        no ruido gaussiano denso sobre todas las neuronas.
        """
        out = torch.zeros(self.n, device=self.device)
        idx = torch.randint(0, self.n, (n_kicks,), device=self.device)
        out.index_add_(0, idx, torch.full((n_kicks,), amplitude, device=self.device))
        return out
