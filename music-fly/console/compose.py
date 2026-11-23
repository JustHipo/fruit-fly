"""La logica de interpretacion (traza -> composicion), separada de
compose_from_trace.py para poder correrla tambien sobre variantes de la
traza (cerebro congelado, ruido) en el test de honestidad de 11.1.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

import numpy as np

from console.decoder import ConsoleDecoder
from console.vocabulary import (
    INSTRUMENTS,
    METERS,
    MIN_NOTE_GAP_STEPS,
    TEMPO_RANGE,
    VELOCITY_RANGE,
    remap,
    scale_pitch,
    zone_index,
)

LEG_T1L, LEG_T1R, LEG_T2L, LEG_T2R, LEG_T3L, LEG_T3R = range(6)
N_DEGREES = 10
BALANCE_THRESHOLD = 2  # ver LiveNoteGate.maybe_fire - bajado de 4, reparte mas rapido

# T2 izquierda elige entre los instrumentos de la paleta Y una zona de
# silencio (una mas, en el mismo continuo - no una regla aparte, sigue
# siendo 7.5: zona continua, nunca menu). Sin esto la mosca elegia SIEMPRE
# algun instrumento, nunca callaba - el usuario pidio que pudiera dejar
# huecos y compases vacios de verdad, decodificados, no forzados.
N_INSTRUMENT_ZONES = len(INSTRUMENTS) + 1
REST_ZONE = 0


def _pick_instrument_zone(legs, track_counts=None):
    """Devuelve el Instrument elegido, o None si T2 izquierda cayo en la
    zona de silencio. Compartido entre LiveNoteGate y compose_from_legs."""
    zone = zone_index(legs[LEG_T2L].x, N_INSTRUMENT_ZONES)
    if zone == REST_ZONE:
        return None
    chosen = INSTRUMENTS[zone - 1]
    if track_counts is None:
        return chosen
    least = min(INSTRUMENTS, key=lambda inst: track_counts.get(inst.track, 0))
    if track_counts.get(chosen.track, 0) - track_counts.get(least.track, 0) > BALANCE_THRESHOLD:
        return least
    return chosen


@dataclass(frozen=True)
class Note:
    track: int
    start_s: float
    end_s: float
    pitch: int
    velocity: int


@dataclass(frozen=True)
class ComposeResult:
    notes: tuple[Note, ...]
    meter_name: str
    tempo_bpm: float


def compose(times: list[float], z_values: list[np.ndarray], seed: int = 0) -> ComposeResult:
    """La misma logica que usa compose_from_trace.py, aislada para poder
    correrla sobre cualquier secuencia de z (real, congelada, ruido)."""
    decoder = ConsoleDecoder(n_pop=len(z_values[0]), seed=seed)
    decoded = [decoder(z) for z in z_values]
    return compose_from_legs(times, decoded)


def meter_and_tempo(decoded) -> tuple:
    """La parte de compose_from_legs que decide compas y tempo, aislada para
    poder calcularla una sola vez al arrancar una sesion en vivo (no hace
    falta cuerpo fisico para esto: T3R es continuo, no depende de contacto)."""
    meter_zones = [zone_index(legs[LEG_T3R].x, len(METERS)) for legs in decoded]
    meter = METERS[Counter(meter_zones).most_common(1)[0][0]]
    tempo = sum(remap(legs[LEG_T3R].y, *TEMPO_RANGE) for legs in decoded) / len(decoded)
    return meter, tempo


class LiveNoteGate:
    """Version en vivo, cuadro a cuadro, del gate de notas de
    compose_from_legs: mismo cooldown, misma escala, pero sin poder mirar el
    futuro (usada por live_view_console.py, que procesa un cuadro por vez a
    medida que la fisica real lo confirma). La duracion queda fija en un paso
    de grilla en vez de contar cuadros de T1R.press consecutivos hacia
    adelante, porque en vivo todavia no se sabe cuanto va a durar el
    contacto."""

    def __init__(self, meter, tempo: float):
        self.meter = meter
        self.tempo = tempo
        self.grid_step_s = 30.0 / tempo
        self.min_gap_s = MIN_NOTE_GAP_STEPS * self.grid_step_s
        self.last_note_t = -self.min_gap_s

    def maybe_fire(self, t: float, legs, track_counts: dict[int, int] | None = None) -> Note | None:
        """`track_counts` es cuantas notas tiene cada pista hasta ahora, para
        el balanceo de `_pick_instrument_zone`. NUNCA se satura un canal para
        siempre (round-robin por carga si la diferencia es grande), pero
        tampoco se fuerza a tocar: si T2 izquierda cae en la zona de
        silencio, esta nota se salta - un compas vacio real, decodificado,
        no forzado."""
        t1l = legs[LEG_T1L]
        if not t1l.press or (t - self.last_note_t) < self.min_gap_s:
            return None

        instrument = _pick_instrument_zone(legs, track_counts)
        if instrument is None:
            return None  # T2 izquierda eligio silencio este gesto

        degree = round(remap(t1l.y, 0, N_DEGREES - 1))
        velocity = round(remap(t1l.x, *VELOCITY_RANGE))
        pitch = scale_pitch(degree, instrument.base_note)
        start = round(t / self.grid_step_s) * self.grid_step_s
        end = start + self.grid_step_s
        self.last_note_t = t
        return Note(instrument.track, start, end, pitch, velocity)


def compose_from_legs(times: list[float], decoded) -> ComposeResult:
    """Igual que `compose()`, pero recibe directamente una secuencia de seis
    LegTarget por cuadro en vez de z crudo. La usa `compose()` (con los
    LegTarget que salen del decodificador tal cual) y tambien
    music-fly/console/body_compose.py (con los LegTarget REALES, verificados
    por fisica: solo press=True si hubo contacto de verdad, y x/y de donde la
    garra realmente toco, no de donde el decodificador queria que tocara).
    """
    meter_zones = [zone_index(legs[LEG_T3R].x, len(METERS)) for legs in decoded]
    meter = METERS[Counter(meter_zones).most_common(1)[0][0]]
    tempo = sum(remap(legs[LEG_T3R].y, *TEMPO_RANGE) for legs in decoded) / len(decoded)
    grid_step_s = 30.0 / tempo
    min_gap_s = MIN_NOTE_GAP_STEPS * grid_step_s

    notes: list[Note] = []
    last_note_t = -min_gap_s
    n = len(decoded)
    for i, legs in enumerate(decoded):
        t = times[i]
        t1l = legs[LEG_T1L]
        if not t1l.press or (t - last_note_t) < min_gap_s:
            continue

        instrument = _pick_instrument_zone(legs)
        if instrument is None:
            continue  # T2 izquierda eligio silencio este gesto

        degree = round(remap(t1l.y, 0, N_DEGREES - 1))
        velocity = round(remap(t1l.x, *VELOCITY_RANGE))
        pitch = scale_pitch(degree, instrument.base_note)

        run_steps = 1
        j = i + 1
        while j < n and decoded[j][LEG_T1R].press and run_steps < meter.steps_per_bar:
            run_steps += 1
            j += 1

        start = round(t / grid_step_s) * grid_step_s
        end = start + max(1, run_steps) * grid_step_s
        notes.append(Note(instrument.track, start, end, pitch, velocity))
        last_note_t = t

    return ComposeResult(notes=tuple(notes), meter_name=meter.name, tempo_bpm=tempo)
