"""Background tegrastats reader for per-rail power and CPU frequency.

Extends jetson_evaluation/tegrastats_power.py in two ways needed here:
  - it parses every VDD_* rail, not only board input, so the CPU rail
    (VDD_CPU_GPU_CV) can be used instead of whole-board power;
  - it runs one long-lived reader thread whose samples are sliced by monotonic
    timestamp, so many short measurement windows share a single tegrastats
    process and no start/stop transient lands inside a window.
"""

from __future__ import annotations

import re
import shutil
import signal
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# "VDD_IN 3951mW/3951mW" and "POM_5V_IN 3210/3400" both occur in the wild.
_RAIL_RE = re.compile(r"\b((?:VDD|POM|VIN)_[A-Z0-9_]+)\s+(\d+)(?:mW)?/(\d+)(?:mW)?")
# "CPU [16%@1036,22%@1036,...]"
_CPU_RE = re.compile(r"CPU \[([^\]]*)\]")
_CORE_RE = re.compile(r"(\d+)%@(\d+)|off")
_TEMP_RE = re.compile(r"\b([a-z0-9]+)@([\d.]+)C")


@dataclass
class Sample:
    t: float
    rails_w: Dict[str, float] = field(default_factory=dict)
    core_util: List[Optional[float]] = field(default_factory=list)
    core_mhz: List[Optional[float]] = field(default_factory=list)
    temps_c: Dict[str, float] = field(default_factory=dict)


def parse_line(line: str, t: float) -> Optional[Sample]:
    rails = {m.group(1): float(m.group(2)) / 1000.0 for m in _RAIL_RE.finditer(line)}
    if not rails:
        return None
    util: List[Optional[float]] = []
    mhz: List[Optional[float]] = []
    m = _CPU_RE.search(line)
    if m:
        for part in m.group(1).split(","):
            part = part.strip()
            if part == "off":
                util.append(None)
                mhz.append(None)
                continue
            cm = re.match(r"(\d+)%@(\d+)", part)
            if cm:
                util.append(float(cm.group(1)))
                mhz.append(float(cm.group(2)))
            else:
                util.append(None)
                mhz.append(None)
    temps = {tm.group(1): float(tm.group(2)) for tm in _TEMP_RE.finditer(line)}
    return Sample(t=t, rails_w=rails, core_util=util, core_mhz=mhz, temps_c=temps)


class RailSampler:
    """One tegrastats process, one reader thread, samples kept in memory."""

    def __init__(self, interval_ms: int = 100):
        self.interval_ms = int(interval_ms)
        self._proc: Optional[subprocess.Popen] = None
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._samples: List[Sample] = []
        self._stop = threading.Event()

    @staticmethod
    def available() -> bool:
        return shutil.which("tegrastats") is not None

    def start(self) -> None:
        if not self.available():
            raise FileNotFoundError("tegrastats not found in PATH")
        self._proc = subprocess.Popen(
            ["tegrastats", "--interval", str(self.interval_ms)],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        self._thread = threading.Thread(target=self._read, daemon=True)
        self._thread.start()

    def _read(self) -> None:
        assert self._proc is not None and self._proc.stdout is not None
        for raw in self._proc.stdout:
            if self._stop.is_set():
                return
            s = parse_line(raw.decode("utf-8", errors="replace"), time.monotonic())
            if s is not None:
                with self._lock:
                    self._samples.append(s)

    def stop(self) -> None:
        self._stop.set()
        if self._proc is not None:
            try:
                self._proc.send_signal(signal.SIGINT)
                self._proc.wait(timeout=2.0)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            self._proc = None

    def window(self, t0: float, t1: float) -> List[Sample]:
        with self._lock:
            return [s for s in self._samples if t0 <= s.t <= t1]

    def n_samples(self) -> int:
        with self._lock:
            return len(self._samples)


def mean_power_w(samples: List[Sample], rail: str) -> Optional[float]:
    vals = [s.rails_w[rail] for s in samples if rail in s.rails_w]
    if not vals:
        return None
    return sum(vals) / len(vals)


def trapezoid_energy_j(samples: List[Sample], rail: str) -> Optional[float]:
    pts = [(s.t, s.rails_w[rail]) for s in samples if rail in s.rails_w]
    if len(pts) < 2:
        return None
    e = 0.0
    for (t0, p0), (t1, p1) in zip(pts, pts[1:]):
        dt = t1 - t0
        if dt > 0:
            e += 0.5 * (p0 + p1) * dt
    return e


def busy_core_mhz(samples: List[Sample], min_util: float = 50.0) -> Optional[float]:
    """Mean clock of cores that were actually loaded, to check f stayed pinned."""
    vals = []
    for s in samples:
        for u, f in zip(s.core_util, s.core_mhz):
            if u is not None and f is not None and u >= min_util:
                vals.append(f)
    if not vals:
        return None
    return sum(vals) / len(vals)


def max_temp_c(samples: List[Sample], key: str = "cpu") -> Optional[float]:
    vals = [s.temps_c[key] for s in samples if key in s.temps_c]
    return max(vals) if vals else None
