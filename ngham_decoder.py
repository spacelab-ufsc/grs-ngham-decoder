import ctypes
from pyngham import PyNGHam

# C sync word
lib = ctypes.CDLL("./libsyncword.so")
lib.syncword_create.argtypes = [ctypes.POINTER(ctypes.c_uint8), ctypes.c_size_t]
lib.syncword_create.restype  = ctypes.c_void_p
lib.syncword_detect.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                ctypes.c_size_t, ctypes.POINTER(ctypes.c_uint8)]
lib.syncword_detect.restype  = ctypes.c_int

SYNC_BYTES   = (0x5D, 0xE6, 0x2A, 0x7E)
OVERLAP_SIZE = 4
MAX_ERRORS   = 1


class NGHamFeeder:
    def __init__(self):
        self.pngh = PyNGHam()
        sw_arr = (ctypes.c_uint8 * len(SYNC_BYTES))(*SYNC_BYTES)
        self.sw = lib.syncword_create(sw_arr, len(SYNC_BYTES))
        self.overlap   = b''
        self.searching = True

    def feed(self, new_bytes):
        buf = bytes(self.overlap) + bytes(new_bytes)
        self.overlap = b''
        pos = 0

        while pos < len(buf):
            if self.searching:
                window = buf[pos:]
                arr = (ctypes.c_uint8 * len(window))(*window)
                offset = lib.syncword_detect(self.sw, MAX_ERRORS, len(window), arr)
                if offset < 0:
                    # keep only unsearched tail, in case the sync word is split
                    self.overlap = window[-OVERLAP_SIZE:]
                    return
                pos += offset
                self.searching = False
                continue

            payload, errors, error_pos = self.pngh.decode_byte(buf[pos])
            pos += 1
            if payload:
                self.handle_packet(payload, errors, error_pos)
                self.searching = True
            elif errors == -1:       # packet finished but failed its CRC
                self.searching = True

    def handle_packet(self, payload, errors, error_pos):
        print(f"Packet:{bytes(payload)}\n{errors} errors in positions {error_pos}")
        # TODO: Data should be passed forward to netwrok layer protocol