"""Tests for the C sync word detector (syncword.c), called through ctypes."""
import ctypes
import itertools

import pytest

from helpers import NOISE, SYNC, flip_bits


class Detector:
    """Thin ctypes wrapper around one SyncWord object."""

    def __init__(self, lib, sync: bytes):
        self.lib = lib
        arr = (ctypes.c_uint8 * len(sync)).from_buffer_copy(sync)
        self.handle = lib.syncword_create(arr, len(sync))
        assert self.handle, "syncword_create returned NULL"

    def detect(self, stream: bytes, max_errors: int = 1) -> int:
        arr = (ctypes.c_uint8 * len(stream)).from_buffer_copy(stream)
        return self.lib.syncword_detect(self.handle, max_errors, len(stream), arr)

    def destroy(self):
        self.lib.syncword_destroy(self.handle)


@pytest.fixture(scope="module")
def lib(libsyncword_path):
    lib = ctypes.CDLL(str(libsyncword_path))
    lib.syncword_create.argtypes = [ctypes.POINTER(ctypes.c_uint8), ctypes.c_size_t]
    lib.syncword_create.restype = ctypes.c_void_p
    lib.syncword_detect.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                    ctypes.c_size_t, ctypes.POINTER(ctypes.c_uint8)]
    lib.syncword_detect.restype = ctypes.c_int
    lib.syncword_destroy.argtypes = [ctypes.c_void_p]
    lib.syncword_destroy.restype = None
    return lib


@pytest.fixture
def make_detector(lib):
    created = []

    def factory(sync: bytes = SYNC) -> Detector:
        det = Detector(lib, sync)
        created.append(det)
        return det

    yield factory
    for det in created:
        det.destroy()


@pytest.fixture
def detector(make_detector):
    return make_detector(SYNC)


# --- return value: offset of the first byte AFTER the sync word -------------

def test_match_at_start_returns_offset_after_sync(detector):
    assert detector.detect(SYNC + b"\xAA\xBB") == len(SYNC)


def test_match_midstream_returns_offset_after_sync(detector):
    assert detector.detect(NOISE + SYNC + b"\xAA\xBB") == len(NOISE) + len(SYNC)


def test_match_at_very_end_of_stream(detector):
    stream = NOISE + SYNC
    assert detector.detect(stream) == len(stream)


def test_stream_exactly_the_sync_word(detector):
    assert detector.detect(SYNC) == len(SYNC)


def test_partial_sync_prefix_before_real_sync(detector):
    assert detector.detect(SYNC[:3] + SYNC) == 3 + len(SYNC)


# --- no match ----------------------------------------------------------------

def test_no_sync_word_in_stream(detector):
    assert detector.detect(NOISE * 3) == -1


def test_empty_stream(detector):
    assert detector.detect(b"") == -1


def test_stream_shorter_than_sync_word(detector):
    assert detector.detect(SYNC[:3]) == -1


def test_truncated_sync_word_at_end_is_not_a_match(detector):
    assert detector.detect(NOISE + SYNC[:3]) == -1


# --- bit error tolerance -----------------------------------------------------

@pytest.mark.parametrize("bit", range(32))
def test_single_bit_error_is_tolerated_with_max_errors_1(detector, bit):
    stream = NOISE + flip_bits(SYNC, bit) + b"\x00"
    assert detector.detect(stream, max_errors=1) == len(NOISE) + len(SYNC)


@pytest.mark.parametrize("bit", range(32))
def test_single_bit_error_rejected_with_max_errors_0(detector, bit):
    assert detector.detect(NOISE + flip_bits(SYNC, bit), max_errors=0) == -1


def test_every_two_bit_error_pattern_is_rejected_with_max_errors_1(detector):
    accepted = [
        pair for pair in itertools.combinations(range(32), 2)
        if detector.detect(NOISE + flip_bits(SYNC, *pair), max_errors=1) != -1
    ]
    assert accepted == []


@pytest.mark.parametrize("n_errors", [0, 1, 2, 3, 4])
def test_threshold_is_inclusive(detector, n_errors):
    corrupted = flip_bits(SYNC, *[b * 7 for b in range(n_errors)])  # spread over bytes
    assert detector.detect(corrupted, max_errors=n_errors) == len(SYNC)
    if n_errors:
        assert detector.detect(corrupted, max_errors=n_errors - 1) == -1


# --- which match is returned -------------------------------------------------

def test_first_of_several_matches_wins(detector):
    assert detector.detect(SYNC + b"\x00" + SYNC) == len(SYNC)


def test_earliest_fuzzy_match_wins_over_later_exact_match(detector):
    """Documents current behaviour: the scan stops at the first window within
    tolerance, even if a perfect match appears later in the stream."""
    stream = flip_bits(SYNC, 5) + NOISE + SYNC
    assert detector.detect(stream, max_errors=1) == len(SYNC)


# --- object lifecycle --------------------------------------------------------

def test_sync_word_bytes_are_copied_on_create(lib):
    arr = (ctypes.c_uint8 * len(SYNC))(*SYNC)
    handle = lib.syncword_create(arr, len(SYNC))
    try:
        for i in range(len(SYNC)):   # caller's buffer changes after create
            arr[i] = 0x00
        stream = (ctypes.c_uint8 * len(SYNC)).from_buffer_copy(SYNC)
        assert lib.syncword_detect(handle, 0, len(SYNC), stream) == len(SYNC)
    finally:
        lib.syncword_destroy(handle)


def test_detector_can_be_reused(detector):
    assert detector.detect(SYNC) == 4
    assert detector.detect(NOISE) == -1
    assert detector.detect(NOISE + SYNC) == len(NOISE) + 4


def test_destroy_null_is_safe(lib):
    lib.syncword_destroy(None)


@pytest.mark.parametrize("sync", [b"\x7E", b"\x5D\xE6", bytes(range(1, 9))])
def test_other_sync_word_lengths(make_detector, sync):
    det = make_detector(sync)
    assert det.detect(NOISE + sync + b"\xFF") == len(NOISE) + len(sync)
    assert det.detect(NOISE, max_errors=0) == -1
