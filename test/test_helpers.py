"""Sanity checks on the test fixtures themselves."""
from helpers import NOISE, SYNC, bit_distance, flip_bits


def test_noise_never_looks_like_a_sync_word():
    windows = (NOISE[i:i + 4] for i in range(len(NOISE) - 3))
    assert min(bit_distance(w, SYNC) for w in windows) > 1


def test_flip_bits_is_msb_first():
    assert flip_bits(b"\x00\x00", 0) == b"\x80\x00"
    assert flip_bits(b"\x00\x00", 15) == b"\x00\x01"
