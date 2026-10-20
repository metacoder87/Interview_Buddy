"""WASAPI loopback capture -> continuous 16 kHz mono float32 stream.

Captures exactly what is rendered to the default audio endpoint (the
interviewer in Zoom/Teams/Meet) and structurally ignores microphone input —
the mic is a separate capture endpoint we never open.

Known WASAPI quirk handled here: loopback only delivers buffers while
playback is active. `LoopbackCapture.read()` therefore reports wall-clock
elapsed time so the consumer can synthesize silence for gaps, keeping VAD /
endpoint timing accurate (ARCHITECTURE.md §2.1).
"""
from __future__ import annotations

import queue
import threading
import time

import numpy as np

TARGET_RATE = 16000
CAPTURE_RATE = 48000  # WASAPI shared-mode rate on Windows


def find_loopback_device():
    """Locate the loopback device for the default render endpoint."""
    import pyaudiowpatch as pyaudio

    p = pyaudio.PyAudio()
    try:
        if hasattr(p, "get_default_wasapi_loopback"):
            dev = p.get_default_wasapi_loopback()
            if dev:
                return p, dev
    except Exception:
        pass

    try:
        wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)
        default_out = p.get_device_info_by_index(wasapi_info["defaultOutputDevice"])
        for dev in p.get_loopback_device_info_generator():
            if default_out["name"] in dev["name"]:
                return p, dev
    except Exception:
        pass

    for dev in p.get_loopback_device_info_generator():
        return p, dev

    raise RuntimeError("No WASAPI loopback device found")


def _downmix_and_resample(samples: np.ndarray, channels: int, in_rate: int) -> np.ndarray:
    """Downmix multi-channel audio to mono and resample to TARGET_RATE (16000)."""
    if len(samples) == 0:
        return np.zeros(0, dtype=np.float32)
    if channels > 1:
        # Reshape to (frames, channels) and average across channels
        n_frames = len(samples) // channels
        samples = samples[: n_frames * channels].reshape(-1, channels).mean(axis=1)

    # Decimate if 48000 -> 16000
    if in_rate == 48000:
        n = len(samples) - (len(samples) % 3)
        if n <= 0:
            return np.zeros(0, dtype=np.float32)
        return samples[:n].reshape(-1, 3).mean(axis=1).astype(np.float32)
    elif in_rate == TARGET_RATE:
        return samples.astype(np.float32)
    else:
        # Simple linear interpolation fallback for non-48k rates
        duration = len(samples) / in_rate
        target_len = int(duration * TARGET_RATE)
        if target_len <= 0:
            return np.zeros(0, dtype=np.float32)
        indices = np.linspace(0, len(samples) - 1, target_len)
        return np.interp(indices, np.arange(len(samples)), samples).astype(np.float32)


class LoopbackCapture:
    """Threaded WASAPI loopback capture. Consume via .read()."""

    def __init__(self):
        import pyaudiowpatch as pyaudio

        self._pa = pyaudio
        # Initialize audio capture; fall back to dummy device if loopback not found
        try:
            self._p, self._dev = find_loopback_device()
            self.device_name: str = self._dev["name"]
            self.channels: int = int(self._dev.get("maxInputChannels", 2))
            self.rate: int = int(self._dev.get("defaultSampleRate", CAPTURE_RATE))
            self.frames_per_buffer: int = int(self.rate * 0.02)  # 20 ms chunk
            self._stream = self._p.open(
                format=self._pa.paFloat32,
                channels=self.channels,
                rate=self.rate,
                input=True,
                input_device_index=self._dev["index"],
                frames_per_buffer=self.frames_per_buffer,
            )
        except Exception as e:
            print(f"[audio] fallback init (no loopback device): {e}", flush=True)
            # Use a dummy device configuration
            self._p = None
            self._dev = {"index": 0, "name": "dummy", "maxInputChannels": 2, "defaultSampleRate": CAPTURE_RATE}
            self.device_name = self._dev["name"]
            self.channels = int(self._dev.get("maxInputChannels", 2))
            self.rate = int(self._dev.get("defaultSampleRate", CAPTURE_RATE))
            self.frames_per_buffer = int(self.rate * 0.02)
            self._stream = None

        self._q: "queue.Queue[np.ndarray]" = queue.Queue()
        self._running = True
        self._stopped = False
        self._last_read_time = time.time()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        print(f"[audio] loopback capture started on {self.device_name!r} (channels={self.channels}, rate={self.rate})", flush=True)

    def _run(self):
        while self._running:
            if self._stream is None:
                time.sleep(0.02)
                continue
            try:
                # WASAPI loopback streams in Windows block on read() if no audio is actively rendering.
                # Check get_read_available() if available to avoid hanging during silence.
                get_avail = getattr(self._stream, "get_read_available", None)
                if callable(get_avail):
                    avail = get_avail()
                    if avail < self.frames_per_buffer:
                        time.sleep(0.01)
                        continue
                    to_read = self.frames_per_buffer
                else:
                    to_read = self.frames_per_buffer

                data = self._stream.read(to_read, exception_on_overflow=False)
            except Exception:
                time.sleep(0.02)
                continue
            if not self._running:
                break
            samples = np.frombuffer(data, dtype=np.float32).copy()
            if len(samples):
                mono_16k = _downmix_and_resample(samples, self.channels, self.rate)
                if len(mono_16k):
                    self._q.put(mono_16k)

    def read(self, timeout: float = 0.02) -> tuple[np.ndarray, float]:
        """Drain all buffered 16 kHz samples. Returns (samples, wall_seconds since last read)."""
        now = time.time()
        elapsed = now - self._last_read_time
        self._last_read_time = now

        chunks: list[np.ndarray] = []
        try:
            chunks.append(self._q.get(timeout=timeout))
        except queue.Empty:
            pass
        while True:
            try:
                chunks.append(self._q.get_nowait())
            except queue.Empty:
                break
        out = np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32)
        return out, elapsed

    def stop(self):
        if self._stopped:
            return
        self._stopped = True
        self._running = False
        if hasattr(self, "_thread") and self._thread.is_alive():
            self._thread.join(timeout=0.5)
        try:
            if self._stream:
                if hasattr(self._stream, "is_active") and self._stream.is_active():
                    self._stream.stop_stream()
                self._stream.close()
        except Exception:
            pass
        finally:
            try:
                if self._p:
                    self._p.terminate()
            except Exception:
                pass
        print("[audio] loopback capture stopped", flush=True)
