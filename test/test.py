import ctypes
from pyngham import PyNGHam

# ── Load shared library ───────────────────────────────────────────
lib = ctypes.CDLL("./libsyncword.so")
lib.syncword_create.argtypes = [ctypes.POINTER(ctypes.c_uint8), ctypes.c_size_t]
lib.syncword_create.restype  = ctypes.c_void_p
lib.syncword_detect.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                 ctypes.c_size_t, ctypes.POINTER(ctypes.c_uint8)]
lib.syncword_detect.restype  = ctypes.c_int

# ── Constants ─────────────────────────────────────────────────────
SYNC_BYTES = bytes([0x5D, 0xE6, 0x2A, 0x7E])
MAX_ERRORS = 1
# ── Build the test byte array ─────────────────────────────────────
pngh = PyNGHam()
payload     = b"SPACELAB"
encoded     = bytes(pngh.encode(payload))       # encode

random_preamble = bytes([0xAB, 0x12, 0x7F, 0x00, 0xCC, 0xFF])
byte_array_test = random_preamble + encoded

print(f"Preamble  : {random_preamble.hex(' ')}")
print(f"Sync word : {SYNC_BYTES.hex(' ')}")
print(f"Encoded   : {encoded.hex(' ')}")
print(f"Full array: {byte_array_test.hex(' ')}\n")

# ── Test function ─────────────────────────────────────────────────
def test(buf: bytes):
    # --- syncword detection ---
    sw_arr = (ctypes.c_uint8 * len(SYNC_BYTES))(*SYNC_BYTES)
    sw     = lib.syncword_create(sw_arr, len(SYNC_BYTES))

    buf_arr = (ctypes.c_uint8 * len(buf))(*buf)
    offset  = lib.syncword_detect(sw, MAX_ERRORS, len(buf), buf_arr)

    if offset < 0:
        print("FAIL — sync word not found")
        return

    print(f"PASS — sync word found, payload starts at byte index {offset}")

    # --- NGHam decode ---
    pngh   = PyNGHam()
    result = None
    for b in buf[offset:]:
        result = pngh.decode_byte(b)
        if result[0]:           # payload is non-empty → packet complete
            break

    if result and result[0]:
        decoded_payload, errors, error_pos = result
        decoded_bytes = bytes(decoded_payload)
        print(f"PASS — decoded payload : {decoded_bytes}")
        print(f"       Reed-Solomon    : {errors} errors at positions {error_pos}")

        if decoded_bytes == payload:
            print("PASS — decoded payload matches original")
        else:
            print(f"FAIL — mismatch: expected {payload}, got {decoded_bytes}")
    else:
        print("FAIL — NGHam decode produced no packet")

# ── Run ───────────────────────────────────────────────────────────
test(byte_array_test)