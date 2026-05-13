"""SoundListener – real-time audio monitoring with cross-correlation matching.

FAITHFUL port of ok-nte's SoundListener.  Monitors the default audio loopback
device, applies a Butterworth bandpass filter, maintains a ring buffer, and
checks for dodge / counter sound events via normalised cross-correlation
against pre-computed templates.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Callable

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Butterworth bandpass filter (digital, second-order sections)
# ---------------------------------------------------------------------------
def _butter_bandpass(
    lowcut: float, highcut: float, fs: float, order: int = 4,
) -> tuple[np.ndarray, np.ndarray]:
    """Design a Butterworth bandpass filter, returning (b, a) coefficients."""
    from scipy.signal import butter

    nyq = 0.5 * fs
    low = lowcut / nyq
    high = highcut / nyq
    b, a = butter(order, [low, high], btype="band")
    return b, a


def _butter_bandpass_filter(
    data: np.ndarray, lowcut: float, highcut: float, fs: float, order: int = 4,
) -> np.ndarray:
    """Apply a zero-phase Butterworth bandpass filter."""
    from scipy.signal import butter, sosfiltfilt

    nyq = 0.5 * fs
    low = lowcut / nyq
    high = highcut / nyq
    sos = butter(order, [low, high], btype="band", output="sos")
    return sosfiltfilt(sos, data)


# ---------------------------------------------------------------------------
# Ring buffer
# ---------------------------------------------------------------------------
class RingBuffer:
    """Fixed-size circular buffer for float audio samples."""

    def __init__(self, capacity: int) -> None:
        self._buf: np.ndarray = np.zeros(capacity, dtype=np.float32)
        self._capacity: int = capacity
        self._write_pos: int = 0
        self._size: int = 0

    def write(self, data: np.ndarray) -> None:
        n = len(data)
        if n > self._capacity:
            data = data[-self._capacity:]
            n = self._capacity
        end = self._write_pos + n
        if end <= self._capacity:
            self._buf[self._write_pos:end] = data
        else:
            first = self._capacity - self._write_pos
            self._buf[self._write_pos:] = data[:first]
            self._buf[:end - self._capacity] = data[first:]
        self._write_pos = end % self._capacity
        self._size = min(self._size + n, self._capacity)

    def read(self, n: int | None = None) -> np.ndarray:
        """Read the most recent *n* samples (or all)."""
        if n is None or n > self._size:
            n = self._size
        if n <= 0:
            return np.array([], dtype=np.float32)
        start = (self._write_pos - n) % self._capacity
        if start + n <= self._capacity:
            return self._buf[start:start + n].copy()
        first = self._buf[start:]
        second = self._buf[:n - len(first)]
        return np.concatenate([first, second])

    @property
    def size(self) -> int:
        return self._size

    def clear(self) -> None:
        self._buf.fill(0.0)
        self._write_pos = 0
        self._size = 0


# ---------------------------------------------------------------------------
# Trigger state helper
# ---------------------------------------------------------------------------
@dataclass
class _TriggerState:
    name: str
    template: np.ndarray
    threshold: float
    cooldown_s: float
    callback: Callable[[], None]
    last_fired: float = 0.0


# ---------------------------------------------------------------------------
# SoundListener
# ---------------------------------------------------------------------------
class SoundListener:
    """Listens to the default loopback device for dodge / counter sound cues.

    Parameters
    ----------
    sample_rate : int
        Audio sample rate (Hz).  Default 32000.
    chunk_duration : float
        Processing chunk size in seconds.  Default 0.1.
    buffer_duration : float
        Ring buffer capacity in seconds.  Default 2.0.
    lowcut : float
        Butterworth highpass cutoff (Hz).  Default 300.
    highcut : float
        Butterworth lowpass cutoff (Hz).  Default 8000.
    assets_dir : str
        Path to the assets/sounds directory.
    """

    def __init__(
        self,
        sample_rate: int = 32000,
        chunk_duration: float = 0.1,
        buffer_duration: float = 2.0,
        lowcut: float = 300.0,
        highcut: float = 8000.0,
        assets_dir: str | None = None,
    ) -> None:
        self.sample_rate = sample_rate
        self.chunk_size = int(sample_rate * chunk_duration)
        self.buffer_size = int(sample_rate * buffer_duration)
        self.lowcut = lowcut
        self.highcut = highcut

        if assets_dir is None:
            from module.neverness.globals import GLOBALS
            assets_dir = GLOBALS.assets_dir
        self.assets_dir = os.path.join(assets_dir, "sounds")

        # Ring buffer holding raw (unfiltered) samples
        self._buffer = RingBuffer(self.buffer_size)

        # Trigger registry
        self._triggers: list[_TriggerState] = []
        self._triggers_lock = threading.Lock()

        # Threading
        self._running = False
        self._thread: threading.Thread | None = None
        self._stream = None

        # Preload templates
        self._load_templates()

    # ------------------------------------------------------------------
    # Template loading
    # ------------------------------------------------------------------
    def _load_templates(self) -> None:
        """Load .wav templates and convert to cross-correlation templates."""
        self._templates: dict[str, np.ndarray] = {}

        for name in ("dodge", "counter"):
            npy_path = os.path.join(
                self.assets_dir, f"{name}.wav_{self.sample_rate}_4_1000.npy"
            )
            if os.path.isfile(npy_path):
                try:
                    self._templates[name] = np.load(npy_path)
                    logger.info("Loaded template %s from %s", name, npy_path)
                    continue
                except Exception:
                    logger.exception("Failed to load %s", npy_path)

            # Fallback: generate from .wav via librosa
            wav_path = os.path.join(self.assets_dir, f"{name}.wav")
            if os.path.isfile(wav_path):
                try:
                    import librosa
                    y, sr = librosa.load(wav_path, sr=self.sample_rate, mono=True)
                    y = y.astype(np.float32)
                    if len(y) == 0:
                        logger.warning("%s is empty", wav_path)
                        continue
                    # Bandpass filter
                    y = _butter_bandpass_filter(
                        y, self.lowcut, self.highcut, self.sample_rate, order=4,
                    )
                    # Normalise
                    std = np.std(y)
                    if std > 1e-10:
                        y = (y - np.mean(y)) / std
                    # Cross-correlation template (flip for convolution)
                    template = y[::-1].copy()
                    self._templates[name] = template
                    # Cache the template
                    np.save(npy_path, template)
                    logger.info("Generated template %s -> %s", name, npy_path)
                except Exception:
                    logger.exception("Cannot generate template for %s", name)

    # ------------------------------------------------------------------
    # Trigger management
    # ------------------------------------------------------------------
    def register_trigger(
        self,
        name: str,
        threshold: float,
        cooldown_s: float,
        callback: Callable[[], None],
    ) -> None:
        """Register a sound-event trigger.

        Args:
            name: Template name ("dodge" / "counter").
            threshold: Cross-correlation peak threshold.
            cooldown_s: Minimum seconds between firings.
            callback: Called when triggered.
        """
        template = self._templates.get(name)
        if template is None:
            logger.warning("Unknown trigger name: %s", name)
            return

        with self._triggers_lock:
            self._triggers.append(
                _TriggerState(
                    name=name,
                    template=template,
                    threshold=threshold,
                    cooldown_s=cooldown_s,
                    callback=callback,
                )
            )
        logger.debug("Registered trigger %s (thresh=%.2f)", name, threshold)

    def remove_trigger(self, name: str) -> None:
        with self._triggers_lock:
            self._triggers = [t for t in self._triggers if t.name != name]

    # ------------------------------------------------------------------
    # Cross-correlation matching
    # ------------------------------------------------------------------
    def _check_triggers(self, audio_chunk: np.ndarray) -> None:
        """Run cross-correlation against every registered trigger."""
        if len(audio_chunk) < self.chunk_size:
            return

        now = time.time()

        # Apply bandpass filter to the chunk
        filtered = _butter_bandpass_filter(
            audio_chunk, self.lowcut, self.highcut, self.sample_rate, order=4,
        )

        with self._triggers_lock:
            triggers = list(self._triggers)

        for ts in triggers:
            if now - ts.last_fired < ts.cooldown_s:
                continue
            template = ts.template
            tn = len(template)
            if len(filtered) < tn:
                continue

            # Normalised cross-correlation
            corr = np.correlate(filtered, template, mode="valid")
            # Normalise by the energy in the overlapping window
            window_energy = np.sqrt(
                np.convolve(filtered ** 2, np.ones(tn), mode="valid")
            )
            window_energy[window_energy < 1e-10] = 1.0
            norm_corr = corr / (window_energy * np.std(template) * tn)
            peak = float(np.max(np.abs(norm_corr)))

            if peak >= ts.threshold:
                ts.last_fired = now
                logger.info(
                    "Sound trigger %s fired (peak=%.3f)", ts.name, peak
                )
                try:
                    ts.callback()
                except Exception:
                    logger.exception("Trigger callback %s failed", ts.name)

    # ------------------------------------------------------------------
    # Audio capture loop
    # ------------------------------------------------------------------
    def _audio_callback(
        self, indata: np.ndarray, frames: int, time_info, status
    ) -> None:
        """Called by soundcard for each chunk."""
        if status:
            logger.debug("Audio stream status: %s", status)
        # indata shape: (frames, channels)
        if indata.ndim == 2 and indata.shape[1] > 0:
            mono = indata[:, 0].astype(np.float32)
        else:
            mono = indata.ravel().astype(np.float32)
        self._buffer.write(mono)

    def _run_loop(self) -> None:
        """Background thread that processes the ring buffer."""
        logger.info("SoundListener loop started")
        while self._running:
            time.sleep(0.05)  # 50 ms polling
            try:
                if self._buffer.size >= self.chunk_size:
                    chunk = self._buffer.read(self.chunk_size)
                    self._check_triggers(chunk)
            except Exception:
                logger.exception("Error in SoundListener loop")
        logger.info("SoundListener loop stopped")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def start(self) -> None:
        if self._running:
            return
        self._running = True

        try:
            import soundcard as sc

            default_mic = sc.default_speaker()
            if default_mic is None:
                logger.error("No loopback device found")
                self._running = False
                return

            self._stream = default_mic.recorder(
                samplerate=self.sample_rate,
                channels=1,
                blocksize=self.chunk_size,
            )
            self._stream.__enter__()
            # Patch __exit__ to do nothing – we manage lifecycle ourselves
            logger.info("SoundListener using device: %s", default_mic.name)
        except ImportError:
            logger.error("soundcard package not installed")
            self._running = False
            return
        except Exception:
            logger.exception("Failed to open audio device")
            self._running = False
            return

        self._thread = threading.Thread(
            target=self._run_loop, daemon=True, name="SoundListener"
        )
        self._thread.start()

        # Also start a high-rate capture thread
        self._capture_thread = threading.Thread(
            target=self._capture_loop, daemon=True, name="SoundCapture"
        )
        self._capture_thread.start()

    def _capture_loop(self) -> None:
        """High-frequency loop reading raw audio chunks into the buffer."""
        logger.info("Sound capture loop started")
        while self._running and self._stream is not None:
            try:
                data = self._stream.record(numframes=self.chunk_size)
                if data.ndim == 2 and data.shape[1] > 0:
                    mono = data[:, 0].astype(np.float32).ravel()
                else:
                    mono = data.ravel().astype(np.float32)
                self._buffer.write(mono)
            except Exception:
                logger.exception("Audio capture error")
                time.sleep(0.1)
        logger.info("Sound capture loop stopped")

    def stop(self) -> None:
        """Stop listening and release resources."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None
        if getattr(self, "_capture_thread", None) is not None:
            self._capture_thread.join(timeout=2)
            self._capture_thread = None
        if self._stream is not None:
            try:
                self._stream.__exit__(None, None, None)
            except Exception:
                pass
            self._stream = None
        logger.info("SoundListener stopped")
