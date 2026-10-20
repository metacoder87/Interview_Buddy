"""Local STT via faster-whisper (CTranslate2). GPU FP16 when available."""
from __future__ import annotations

import os
import sys

import numpy as np


def _register_nvidia_dll_dirs() -> None:
    """Make cuBLAS & friends from the nvidia-* PyPI wheels loadable on Windows.

    The ctranslate2 CUDA build loads cublas64_12.dll lazily on the first
    inference. If that DLL load happens on a worker thread while another
    thread is inside a COM call (our WASAPI reader), the Windows DLL loader
    can deadlock the whole process. Registering the search path up front
    (main thread, before any inference) avoids both the missing-DLL failure
    and the late load.
    """
    if sys.platform != "win32":
        return
    import importlib.util

    dirs: list[str] = []
    for module in ("nvidia.cublas", "nvidia.cudnn", "nvidia.cuda_runtime",
                   "nvidia.cusolver", "nvidia.cusparse", "nvidia.cuda_nvrtc"):
        try:
            spec = importlib.util.find_spec(module)
            if spec is None or not spec.submodule_search_locations:
                continue
            base = list(spec.submodule_search_locations)[0]
            for sub in ("bin", "lib"):
                d = os.path.join(base, sub)
                if os.path.isdir(d):
                    dirs.append(d)
        except Exception:
            continue
    if not dirs:
        return
    # Plain LoadLibrary() from ctranslate2's C++ only sees the standard
    # search order, so PATH must be set (os.add_dll_directory alone is not
    # consulted by it).
    os.environ["PATH"] = os.pathsep.join(dirs) + os.pathsep + os.environ.get("PATH", "")
    for d in dirs:
        try:
            os.add_dll_directory(d)
        except Exception:
            pass


_register_nvidia_dll_dirs()


def _cuda_available() -> bool:
    try:
        import ctranslate2

        return len(ctranslate2.get_supported_compute_types("cuda")) > 0
    except Exception:
        return False


class Transcriber:
    def __init__(self, model_size: str = "medium"):
        self.device = "cuda" if _cuda_available() else "cpu"
        compute = "float16" if self.device == "cuda" else "int8"
        print(f"[stt] loading {model_size} on {self.device}/{compute} (first run downloads model)...", flush=True)
        from faster_whisper import WhisperModel
        from huggingface_hub import snapshot_download

        # snapshot_download has robust resume/retry and is cached after first fetch.
        model_path = snapshot_download(f"Systran/faster-whisper-{model_size}")
        self.model = WhisperModel(model_path, device=self.device, compute_type=compute)
        print("[stt] ready", flush=True)

    def transcribe(self, audio16k: np.ndarray, vad_filter: bool = True) -> str:
        """Transcribe 16 kHz mono float32. Greedy decode for speed."""
        if len(audio16k) < TARGET_MIN_SAMPLES:
            return ""
        segments, _info = self.model.transcribe(
            audio16k.astype(np.float32),
            language="en",
            vad_filter=vad_filter,
            beam_size=1,
        )
        return " ".join(s.text.strip() for s in segments).strip()


TARGET_MIN_SAMPLES = 1600  # < 0.1 s -> skip
