# ────────────────── tests/test_core.py ───────────────────────

import os
import asyncio
from pathlib import Path

import numpy as np
import pytest

# Import the production code we want to test
from app.core import Core, LoopbackCapture

# ------------------------------------------------------------------
# Helper fixtures – create a Core instance once per module,
# load everything from disk and keep it ready for the rest of the tests.
@pytest.fixture(scope="module")
def core() -> Core:
    """Return a fully initialised Core object."""
    # The constructor will load config.json automatically, so we just call load()
    c = Core()
    c.load(force=True)          # force rebuilds the vectors from scratch
    assert len(c._chunks) > 0, "No chunks were loaded – did load() work?"
    return c

# ------------------------------------------------------------------
# Test that the audio capture works at least in a mock‑fashion.
def test_loopback_capture_init(monkeypatch):
    """Verify that LoopbackCapture can start up and read data."""
    # Create a dummy stream that pretends to return a 16 kHz block of samples
    class DummyStream:
        def __init__(self, frames_per_buffer: int) -> None:
            self.frames = frames_per_buffer

        def read(self, frames_per_buffer: int, exception_on_overflow: bool = False):
            # Return an array of ones – enough to test the pipeline
            data = np.ones(frames_per_buffer * 2, dtype=np.float32).tobytes()
            return data

    # Patch the underlying audio API so that our dummy stream is used.
    cap = LoopbackCapture()
    # patch the stream after construction with our dummy implementation
    cap._stream = DummyStream(cap.frames_per_buffer)

    # Start the loop – the thread should now be alive
    assert cap._running, "LoopbackCapture did not start its thread"

    # Give it a little time to read once
    asyncio.run(asyncio_test_read(cap))

async def asyncio_test_read(cap: LoopbackCapture):
    """Read one block from the dummy stream and check the output shape."""
    # The first call should return a block of length frames_per_buffer*2 samples.
    samples, elapsed = cap.read()
    assert isinstance(samples, np.ndarray), "read() did not return an ndarray"
    # DummyStream returns frames_per_buffer*2 raw float32 samples (stereo 48kHz).
    # _downmix_and_resample: downmix 2ch→mono (÷2), then decimate 48kHz→16kHz (÷3).
    # Net output length = frames_per_buffer * 2 / 2 / 3 = frames_per_buffer // 3
    expected_len = cap.frames_per_buffer // 3
    assert len(samples) == expected_len, f"Expected {expected_len} floats but got {len(samples)}"

# ------------------------------------------------------------------
# Test that the core engine can retrieve a vector for a query.
def test_retrieve(core: Core):
    """A minimal round‑trip through the vector store."""
    q = "Tell me about yourself"
    results = core.retrieve(q, k=3)
    assert isinstance(results, list), "retrieve() did not return a list"
    assert len(results) >= 1, "retrieve returned no chunks for query"

# ------------------------------------------------------------------
# Test that a full answer is streamed back to the websocket.
def test_answer_generation(monkeypatch, core: Core):
    """Verify the end‑to‑end answer pipeline (STT + LLM)."""
    # --------------------------------------------------------------------
    # 1. Mock out the external LLM call – we only need to return some JSON lines
    class DummyLLMResp:
        def __init__(self): self.lines = []

        async def aiter_lines(self):
            # Return three dummy sentences that mimic the real protocol
            for i in range(3):
                yield f'{{"role":"system","content":"dummy sentence {i}"}}'

    class DummyAsyncClient:
        def __init__(self, timeout: int = 0): pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_value, tb):
            return None

        async def stream(self, method: str, url: str, json: dict, timeout: int | None = None):
            # Return a dummy response object
            return DummyLLMResp()

    # Patch the httpx.Client class that the core uses for its LLM call.
    monkeypatch.setattr(
        "httpx.AsyncClient",
        DummyAsyncClient,
        raising=True,
    )

    # --------------------------------------------------------------------
    # 2. Mock the transcription step – we only care that something is returned
    async def dummy_transcribe(audio: np.ndarray, flag: bool) -> str:
        return f"transcribed {len(audio)} samples"

    monkeypatch.setattr(
        core,
        "transcriber",
        DummyLLMResp() if False else type('DummyTrans', (), {"transcribe": dummy_transcribe}),
        raising=True,
    )

    # --------------------------------------------------------------------
    # 3. Run the answer coroutine and wait for it to finish
    asyncio.run(core.answer("Tell me about yourself"))