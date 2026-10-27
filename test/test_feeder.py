"""Tests for NGHamFeeder's sync-search / framing logic.

PyNGHam is replaced by FakePyNGHam (see helpers.py), so these tests exercise
only the feeder: finding the sync word, handing the right bytes to the packet
decoder, and going back to searching afterwards.
"""
import pytest

from helpers import NOISE, SYNC, flip_bits, frame

PAYLOAD = b"hello"
PAYLOAD_2 = b"world!"


def test_decoder_sync_constant_matches_ngham_spec(ngham_decoder):
    assert bytes(ngham_decoder.SYNC_BYTES) == SYNC


# --- searching for the sync word ---------------------------------------------

def test_no_sync_word_means_nothing_is_decoded(fake_harness):
    fake_harness.feed(NOISE * 4)
    assert fake_harness.packets == []
    assert fake_harness.fed == b""
    assert fake_harness.feeder.searching is True


def test_empty_feed_is_harmless(fake_harness):
    fake_harness.feed(b"")
    assert fake_harness.packets == []
    assert fake_harness.feeder.searching is True


def test_packet_after_sync_in_a_single_feed(fake_harness):
    fake_harness.feed(NOISE + SYNC + frame(PAYLOAD))
    assert fake_harness.payloads == [PAYLOAD]


def test_decoder_receives_only_the_bytes_after_the_sync_word(fake_harness):
    fake_harness.feed(NOISE + SYNC + frame(PAYLOAD))
    assert fake_harness.fed == frame(PAYLOAD)


def test_searching_resumes_after_a_packet_is_decoded(fake_harness):
    fake_harness.feed(SYNC + frame(PAYLOAD))
    assert fake_harness.feeder.searching is True


def test_decoding_mode_while_packet_is_incomplete(fake_harness):
    fake_harness.feed(SYNC + frame(PAYLOAD)[:3])
    assert fake_harness.feeder.searching is False
    assert fake_harness.packets == []


@pytest.mark.parametrize("split", [1, 2, 3])
def test_sync_word_split_across_two_feeds(fake_harness, split):
    fake_harness.feed(NOISE + SYNC[:split])
    fake_harness.feed(SYNC[split:] + frame(PAYLOAD))
    assert fake_harness.payloads == [PAYLOAD]


def test_sync_word_found_in_a_later_feed(fake_harness):
    fake_harness.feed(NOISE)
    fake_harness.feed(NOISE)
    fake_harness.feed(SYNC + frame(PAYLOAD))
    assert fake_harness.payloads == [PAYLOAD]


# --- bit errors in the sync word ---------------------------------------------

@pytest.mark.parametrize("bit", range(32))
def test_one_bit_error_in_sync_word_is_accepted(fake_harness, bit):
    fake_harness.feed(NOISE + flip_bits(SYNC, bit) + frame(PAYLOAD))
    assert fake_harness.payloads == [PAYLOAD]


def test_two_bit_errors_in_sync_word_are_rejected(fake_harness):
    fake_harness.feed(NOISE + flip_bits(SYNC, 3, 20) + frame(PAYLOAD))
    assert fake_harness.packets == []
    assert fake_harness.fed == b""


# --- packets that span several feed() calls ----------------------------------

@pytest.mark.parametrize("chunk_size", [1, 2, 3, 5, 7])
def test_stream_delivered_in_small_chunks(fake_harness, chunk_size):
    fake_harness.feed(NOISE + SYNC + frame(PAYLOAD), chunk_size=chunk_size)
    assert fake_harness.payloads == [PAYLOAD]


@pytest.mark.parametrize("chunk_size", [1, 2, 3, 5, 7])
def test_no_byte_is_given_to_the_decoder_twice(fake_harness, chunk_size):
    fake_harness.feed(NOISE + SYNC + frame(PAYLOAD), chunk_size=chunk_size)
    assert fake_harness.fed == frame(PAYLOAD)


def test_feed_ending_exactly_after_the_sync_word(fake_harness):
    fake_harness.feed(NOISE + SYNC)
    fake_harness.feed(frame(PAYLOAD))
    assert fake_harness.fed == frame(PAYLOAD)      # sync bytes must not leak in
    assert fake_harness.payloads == [PAYLOAD]


def test_packet_split_in_the_middle_of_its_payload(fake_harness):
    data = SYNC + frame(PAYLOAD)
    fake_harness.feed(data[:7])
    fake_harness.feed(data[7:])
    assert fake_harness.payloads == [PAYLOAD]


# --- several packets ----------------------------------------------------------

def test_two_packets_in_separate_feeds(fake_harness):
    fake_harness.feed(NOISE + SYNC + frame(PAYLOAD))
    fake_harness.feed(NOISE + SYNC + frame(PAYLOAD_2))
    assert fake_harness.payloads == [PAYLOAD, PAYLOAD_2]


def test_two_packets_back_to_back_in_one_feed(fake_harness):
    fake_harness.feed(SYNC + frame(PAYLOAD) + SYNC + frame(PAYLOAD_2))
    assert fake_harness.payloads == [PAYLOAD, PAYLOAD_2]


def test_garbage_between_packets_in_one_feed_is_skipped(fake_harness):
    fake_harness.feed(SYNC + frame(PAYLOAD) + NOISE + SYNC + frame(PAYLOAD_2))
    assert fake_harness.payloads == [PAYLOAD, PAYLOAD_2]


def test_bytes_after_a_packet_are_searched_not_decoded(fake_harness):
    fake_harness.feed(SYNC + frame(PAYLOAD) + NOISE)
    assert fake_harness.fed == frame(PAYLOAD)


# --- failed packets -----------------------------------------------------------

def test_failed_packet_is_not_reported(fake_harness):
    fake_harness.feed(SYNC + frame(b"BAD payload"))
    assert fake_harness.packets == []


def test_feeder_recovers_after_a_packet_that_fails_its_crc(fake_harness):
    """A failed packet comes back from decode_byte() as ([], -1, []). The
    feeder must go back to hunting for the next sync word, otherwise every
    later packet is decoded out of alignment."""
    fake_harness.feed(SYNC + frame(b"BAD payload"))
    fake_harness.feed(NOISE + SYNC + frame(PAYLOAD))
    assert fake_harness.payloads == [PAYLOAD]


# --- reporting ----------------------------------------------------------------

def test_error_count_and_positions_are_forwarded(fake_harness):
    fake_harness.decoder.errors = 2
    fake_harness.decoder.error_pos = [4, 17]
    fake_harness.feed(SYNC + frame(PAYLOAD))
    assert fake_harness.packets == [(PAYLOAD, 2, [4, 17])]


def test_handle_packet_prints_payload_and_error_info(ngham_decoder, monkeypatch, capsys):
    from helpers import FakePyNGHam
    monkeypatch.setattr(ngham_decoder, "PyNGHam", FakePyNGHam)
    feeder = ngham_decoder.NGHamFeeder()   # real handle_packet, not the harness's
    feeder.handle_packet([0x61, 0x62, 0x63], 2, [4, 17])
    out = capsys.readouterr().out
    assert "abc" in out
    assert "2 errors" in out
    assert "[4, 17]" in out
