import os
import re
import shutil
import signal
import subprocess
import time
from dataclasses import dataclass
from typing import IO, Iterable, Iterator, Optional, Tuple


POWER_RE = re.compile(r"\b(?:POM_5V_IN|VDD_IN)\s+(\d+)(?:mW)?\s*/")


@dataclass(frozen=True)
class PowerSample:
    t_monotonic: float
    watts: float


def _iter_lines(stream: IO[bytes]) -> Iterator[str]:
    while True:
        chunk = stream.readline()
        if not chunk:
            return
        try:
            yield chunk.decode("utf-8", errors="replace").strip()
        except Exception:
            yield str(chunk)


def parse_tegrastats_power_w(line: str) -> Optional[float]:
    """
    Parse `tegrastats` output line for board input power.

    Typical Jetson lines include:
      ... POM_5V_IN 3210/3400 ...
      ... POM_5V_IN 3210mW/3400mW ...

    Returns power in **Watts** (float) or None if not present.
    """
    m = POWER_RE.search(line)
    if not m:
        return None
    mw = float(m.group(1))
    return mw / 1000.0


class TegraStatsPowerSampler:
    """
    Samples Jetson power using `tegrastats --interval <ms>`.

    This is intentionally dependency-free and tolerant to slight formatting changes.
    """

    def __init__(self, interval_ms: int = 200):
        self.interval_ms = int(interval_ms)
        self._proc: Optional[subprocess.Popen[bytes]] = None

    def available(self) -> bool:
        return shutil.which("tegrastats") is not None

    def start(self) -> None:
        if self._proc is not None:
            raise RuntimeError("Sampler already started")
        if not self.available():
            raise FileNotFoundError("tegrastats not found in PATH")

        # tegrastats runs until killed; we capture stdout for parsing.
        self._proc = subprocess.Popen(
            ["tegrastats", "--interval", str(self.interval_ms)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=os.environ.copy(),
        )

        if self._proc.stdout is None:
            raise RuntimeError("Failed to capture tegrastats stdout")

    def stop(self) -> None:
        if self._proc is None:
            return
        try:
            # SIGINT tends to produce a clean exit.
            self._proc.send_signal(signal.SIGINT)
            self._proc.wait(timeout=2.0)
        except Exception:
            try:
                self._proc.kill()
            except Exception:
                pass
        finally:
            self._proc = None

    def samples(self) -> Iterator[PowerSample]:
        if self._proc is None or self._proc.stdout is None:
            raise RuntimeError("Sampler not started")

        for line in _iter_lines(self._proc.stdout):
            p = parse_tegrastats_power_w(line)
            if p is None:
                continue
            yield PowerSample(t_monotonic=time.monotonic(), watts=p)


def integrate_energy_j(samples: Iterable[PowerSample]) -> Tuple[Optional[float], int]:
    """
    Trapezoidal integration over monotonic timestamps.

    Returns (energy_j, count). If fewer than 2 samples, energy_j is None.
    """
    last: Optional[PowerSample] = None
    e = 0.0
    n = 0
    for s in samples:
        n += 1
        if last is not None:
            dt = s.t_monotonic - last.t_monotonic
            if dt > 0:
                e += 0.5 * (s.watts + last.watts) * dt
        last = s
    if n < 2:
        return None, n
    return e, n
