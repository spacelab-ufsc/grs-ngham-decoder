"""End-to-end tests: real pyngham encoder -> byte stream -> NGHamFeeder.

pyngham's encode() returns preamble (4 x 0xAA) + sync word + codeword, so the
streams below are what a demodulator would hand to the decoder.
"""
import random

import pytest

from helpers import NOISE, SYNC, flip_bits

pyngham = pytest.importorskip("pyngham")

PREAMBLE_LEN = 4


def encode(payload: bytes) -> bytes:
    return bytes(pyngham.PyNGHam().encode(payload))


def test_encoder_output_layout_is_what_these_tests_assume():
    encoded = encode(b"hello")
    assert encoded[:PREAMBLE_LEN] == b"\xAA" * PREAMBLE_LEN
    assert encoded[PREAMBLE_LEN:PREAMBLE_LEN + 4] == SYNC


@pytest.mark.parametrize("size", [1, 5, 28, 60, 100, 220])
def test_roundtrip_for_various_payload_sizes(real_harness, size):
    payload = bytes(random.Random(size).randrange(256) for _ in range(size))
    real_harness.feed(NOISE + encode(payload))
    assert real_harness.payloads == [payload]
    assert real_harness.packets[0][1] == 0       # no errors corrected


@pytest.mark.parametrize("chunk_size", [1, 3, 8, 16])
def test_roundtrip_when_stream_arrives_in_chunks(real_harness, chunk_size):
    real_harness.feed(NOISE + encode(b"chunked delivery"), chunk_size=chunk_size)
    assert real_harness.payloads == [b"chunked delivery"]


def test_one_bit_error_in_sync_word_still_decodes(real_harness):
    stream = bytearray(NOISE + encode(b"noisy sync"))
    sync_at = len(NOISE) + PREAMBLE_LEN
    stream[sync_at:sync_at + 4] = flip_bits(SYNC, 11)
    real_harness.feed(bytes(stream))
    assert real_harness.payloads == [b"noisy sync"]


def test_reed_solomon_corrects_corrupted_bytes(real_harness):
    stream = bytearray(NOISE + encode(b"error correction"))
    for pos in (len(stream) - 10, len(stream) - 25):   # inside the codeword
        stream[pos] ^= 0xFF
    real_harness.feed(bytes(stream))
    assert real_harness.payloads == [b"error correction"]
    assert real_harness.packets[0][1] >= 1             # errors were corrected


def test_two_consecutive_packets_in_one_buffer(real_harness):
    real_harness.feed(encode(b"first") + encode(b"second"))
    assert real_harness.payloads == [b"first", b"second"]


def test_two_packets_with_noise_between_them(real_harness):
    real_harness.feed(NOISE + encode(b"first") + NOISE + encode(b"second") + NOISE)
    assert real_harness.payloads == [b"first", b"second"]
