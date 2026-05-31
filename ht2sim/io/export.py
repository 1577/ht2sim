from __future__ import annotations

import csv

from ..core import constants as C
from ..core.config import Coding
from ..core.memory import bits_to_int
from ..signal.builder import build_waveforms

_US_PER_TO = C.TO_SECONDS * 1e6


def export_frames_csv(result, path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "index", "direction", "kind", "label",
                "t_start_to", "duration_to", "t_start_us", "duration_us",
                "n_bits", "bits", "hex",
            ]
        )
        for i, fr in enumerate(result.frames):
            hex_value = ""
            if fr.bits and len(fr.bits) % 4 == 0:
                hex_value = f"0x{bits_to_int(fr.bits):0{len(fr.bits) // 4}X}"
            w.writerow(
                [
                    i, fr.direction.value, fr.kind.value, fr.label,
                    f"{fr.t_start_to:.3f}", f"{fr.duration_to:.3f}",
                    f"{fr.t_start_us:.3f}", f"{fr.duration_us:.3f}",
                    len(fr.bits), fr.bitstring, hex_value,
                ]
            )


def export_waveform_csv(
    result,
    coding: Coding = Coding.MANCHESTER,
    path: str = "waveform.csv",
    samples_per_to: float = 8.0,
) -> None:
    ws = build_waveforms(result.frames, coding)
    tr, yr = ws.reader.sample(samples_per_to)
    _, yt = ws.tag.sample(samples_per_to)
    n = min(len(tr), len(yr), len(yt))
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["t_to", "t_us", "reader", "tag"])
        for i in range(n):
            w.writerow(
                [f"{tr[i]:.4f}", f"{tr[i] * _US_PER_TO:.4f}", f"{yr[i]:.4f}", f"{yt[i]:.4f}"]
            )
