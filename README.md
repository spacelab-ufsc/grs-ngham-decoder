# GRS NGHam decoder

Streams raw receiver bytes into the NGHam decoder, using a C sync-word detector (`libsyncword.so`) to find packet boundaries in a continuous byte stream before handing bytes off to `pyngham` for NGHam decoding.

## Overview

Radio data arrives as an unstructured byte stream with no guaranteed alignment to packet boundaries. `NGHamFeeder` solves this in two stages:

1. **Sync search** — while `searching` is `True`, incoming bytes are scanned for the custom sync word (`5D E6 2A 7E`, matching NGHam's native sync word) using the C `syncword_detect` function, which tolerates up to `MAX_ERRORS` bit errors.
2. **Decode** — once the sync word is found, subsequent bytes are fed one at a time into `PyNGHam.decode_byte()`, which accumulates them into a packet and returns a decoded payload once a full packet has been received.

The feeder is designed to be called repeatedly with small chunks of newly received bytes (e.g., from a radio/serial callback), maintaining state across calls.

## Requirements

- `libsyncword.so` — compiled C sync-word detector, expected at `./libsyncword.so` relative to the working directory.
- `pyngham` — Python bindings for the NGHam protocol (`PyNGHam` class).

## C library interface

| Function | Signature | Purpose |
|---|---|---|
| `syncword_create` | `(uint8_t *sync_bytes, size_t len) -> void*` | Builds a sync-word matcher handle from the given byte pattern. |
| `syncword_detect` | `(void *sw, int max_errors, size_t buf_len, uint8_t *buf) -> int` | Searches `buf` for the sync word (allowing up to `max_errors` bit errors). Returns the byte offset of the match, or a negative value if not found. |

## Constants

| Name | Value | Meaning |
|---|---|---|
| `SYNC_BYTES` | `(0x5D, 0xE6, 0x2A, 0x7E)` | The sync word to search for — matches NGHam's native sync word. |
| `OVERLAP_SIZE` | `4` | Number of trailing bytes carried over between `feed()` calls, so a sync word split across two calls is not missed. |
| `MAX_ERRORS` | `1` | Maximum bit errors tolerated when matching the sync word. |

## API

### `NGHamFeeder()`

Creates a feeder instance. Initializes the underlying `PyNGHam` decoder and the C sync-word matcher, and starts in the `searching` state (no sync word found yet).

### `feed(new_bytes: bytes) -> None`

Feeds newly received bytes into the feeder. Intended to be called repeatedly as data arrives (e.g., once per received radio frame).

Behavior:

1. Prepends the last `OVERLAP_SIZE` bytes from the previous call (`self.overlap`) to `new_bytes`, so a sync word spanning two `feed()` calls is still detected.
2. **If currently searching for sync:** runs `syncword_detect` over the combined buffer.
   - Not found → saves the last `OVERLAP_SIZE` bytes for the next call and returns.
   - Found → resumes decoding from the offset where the sync word starts, and clears `searching`.
3. Feeds each byte from that point onward into `PyNGHam.decode_byte()`. Whenever a complete packet is returned, calls `handle_packet()` and sets `searching = True` (see **Known limitations** below).
4. Before returning, saves the last `OVERLAP_SIZE` bytes of the combined buffer as `self.overlap` for the next call.

### `handle_packet(payload, errors, error_pos) -> None`

Called whenever `decode_byte()` completes a packet. Currently just prints the payload and error info.

**TODO:** forward `payload` to the network layer protocol instead of printing it (see inline `# TODO` in the source).

## Usage example

```python
feeder = NGHamFeeder()

def on_radio_data(chunk: bytes):
    feeder.feed(chunk)

# e.g., wired into a serial/SDR receive callback
on_radio_data(b'\x5d\xe6\x2a\x7e\x01\x02\x03...')
```

## Known limitations

- **Mid-buffer re-sync isn't immediate.** After a packet completes inside `feed()`, `searching` is set to `True`, but the loop keeps feeding the *remaining* bytes in the current buffer to `decode_byte()` without re-running `syncword_detect` on them. Sync-word search only actually resumes on the *next* call to `feed()`. If more than one packet's worth of data (including a new sync word) arrives within a single `feed()` call, the second packet may not be found correctly.
- **No resync on decode failure.** If `decode_byte()` gets the stream out of alignment (e.g., due to bit errors not caught by NGHam's own error correction), the feeder has no mechanism to detect this and re-search for the sync word — it will keep decoding from the wrong offset until the caller restarts search manually.
- **Working-directory-relative library path.** `./libsyncword.so` is loaded relative to the current working directory, not the module's location, so the feeder will fail to load the library unless run from the expected directory.
- `handle_packet()` is a placeholder — decoded payloads are only printed, not passed on to any consumer.