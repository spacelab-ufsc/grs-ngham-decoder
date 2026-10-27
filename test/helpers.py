"""Shared constants and test doubles for the NGHam decoder tests."""

# NGHam sync word, written out independently of ngham_decoder.SYNC_BYTES so a
# bad edit to the decoder's constant is caught by a test instead of copied here.
SYNC = bytes([0x5D, 0xE6, 0x2A, 0x7E])

# Filler that must never be mistaken for a sync word (checked in test_helpers).
NOISE = bytes([0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x33, 0x66, 0x99, 0xCC])


def bit_distance(a: bytes, b: bytes) -> int:
    """Hamming distance in bits between two equal-length byte strings."""
    return sum(bin(x ^ y).count("1") for x, y in zip(a, b))


def flip_bits(data: bytes, *bit_positions: int) -> bytes:
    """Return a copy of `data` with the given bit positions flipped.

    Bit 0 is the most significant bit of byte 0, bit 8 the MSB of byte 1, ...
    """
    out = bytearray(data)
    for pos in bit_positions:
        out[pos // 8] ^= 0x80 >> (pos % 8)
    return bytes(out)


def frame(payload: bytes) -> bytes:
    """Frame understood by FakePyNGHam: one length byte, then the payload."""
    assert 0 < len(payload) < 256
    return bytes([len(payload)]) + payload


class FakePyNGHam:
    """Stand-in for pyngham.PyNGHam with the same decode_byte() contract.

    Real PyNGHam.decode_byte() returns ([], 0, []) until a whole packet has been
    received, then (payload, n_errors, error_positions). On a CRC failure it
    returns ([], -1, []). This fake reproduces that contract with trivial
    framing (see `frame`), which lets the feeder logic be tested without the
    Reed-Solomon machinery, and records every byte it is given in `fed`.

    A payload starting with BAD_MARKER simulates a packet that fails its CRC.
    """

    BAD_MARKER = b"BAD"

    def __init__(self):
        self.fed = []
        self.errors = 0
        self.error_pos = []
        self._expected = None
        self._buf = []

    def decode_byte(self, byte):
        self.fed.append(byte)
        if self._expected is None:
            self._expected = byte
            return [], 0, []

        self._buf.append(byte)
        if len(self._buf) < self._expected:
            return [], 0, []

        payload, self._buf, self._expected = self._buf, [], None
        if bytes(payload).startswith(self.BAD_MARKER):
            return [], -1, []
        return payload, self.errors, list(self.error_pos)
