"""Fixtures: build libsyncword.so from source and import ngham_decoder against it.

Layout assumed (override the project root with the NGHAM_ROOT env variable):

    <root>/ngham_decoder.py
    <root>/syncword.c  syncword.h
    <root>/tests/      <- this directory
"""
import importlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from helpers import FakePyNGHam

ROOT = Path(os.environ.get("NGHAM_ROOT", Path(__file__).resolve().parent.parent))


@pytest.fixture(scope="session")
def libsyncword_path(tmp_path_factory):
    """Compile syncword.c into a fresh shared library, so tests always run
    against the current source rather than a stale libsyncword.so."""
    compiler = shutil.which("gcc") or shutil.which("cc")
    if compiler is None:
        pytest.skip("no C compiler available to build libsyncword.so")

    out = tmp_path_factory.mktemp("build") / "libsyncword.so"
    result = subprocess.run(
        [compiler, "-shared", "-fPIC", "-Wall", "-I", str(ROOT),
         "-o", str(out), str(ROOT / "syncword.c")],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        pytest.fail(f"failed to build libsyncword.so:\n{result.stderr}")
    return out


@pytest.fixture
def ngham_decoder(libsyncword_path, monkeypatch):
    """Import ngham_decoder fresh. It does CDLL("./libsyncword.so") at import
    time, so the import happens with the build directory as the working dir."""
    monkeypatch.syspath_prepend(str(ROOT))
    monkeypatch.chdir(libsyncword_path.parent)
    sys.modules.pop("ngham_decoder", None)
    module = importlib.import_module("ngham_decoder")
    yield module
    sys.modules.pop("ngham_decoder", None)


class Harness:
    """A feeder plus everything it emitted, for easy assertions."""

    def __init__(self, feeder, decoder=None):
        self.feeder = feeder
        self.decoder = decoder          # FakePyNGHam, or None for the real one
        self.packets = []               # (payload_bytes, errors, error_pos)
        feeder.handle_packet = lambda payload, errors, error_pos: self.packets.append(
            (bytes(payload), errors, list(error_pos))
        )

    @property
    def payloads(self):
        return [p for p, _, _ in self.packets]

    @property
    def fed(self):
        """Bytes the feeder passed to the packet decoder (fake decoder only)."""
        return bytes(self.decoder.fed)

    def feed(self, data: bytes, chunk_size=None):
        if chunk_size is None:
            self.feeder.feed(data)
            return
        for i in range(0, len(data), chunk_size):
            self.feeder.feed(data[i:i + chunk_size])


@pytest.fixture
def fake_harness(ngham_decoder, monkeypatch):
    """NGHamFeeder wired to FakePyNGHam (feeder logic only)."""
    monkeypatch.setattr(ngham_decoder, "PyNGHam", FakePyNGHam)
    feeder = ngham_decoder.NGHamFeeder()
    return Harness(feeder, feeder.pngh)


@pytest.fixture
def real_harness(ngham_decoder):
    """NGHamFeeder wired to the real pyngham decoder."""
    pytest.importorskip("pyngham")
    return Harness(ngham_decoder.NGHamFeeder())
