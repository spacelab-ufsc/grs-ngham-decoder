import ctypes
from pyngham import PyNGHam

# C sync word 
lib = ctypes.CDLL("./libsyncword.so")
lib.syncword_create.argtypes = [ctypes.POINTER(ctypes.c_uint8), ctypes.c_size_t]
lib.syncword_create.restype  = ctypes.c_void_p
lib.syncword_detect.argtypes = [ctypes.c_void_p, ctypes.c_int,
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
        buf = self.overlap + new_bytes
        buf_len = len(buf)

        start = 0
        if self.searching:
            buf_arr = (ctypes.c_uint8 * buf_len)(*buf)
            offset = lib.syncword_detect(self.sw, MAX_ERRORS, buf_len, buf_arr)
            if offset < 0:
                self.overlap = buf[-OVERLAP_SIZE:]
                return
            start = offset
            self.searching = False

        for b in buf[start:]:
            payload, errors, error_pos = self.pngh.decode_byte(b)
            if payload:
                self.handle_packet(payload, errors, error_pos)
                self.searching = True   # 

        self.overlap = buf[-OVERLAP_SIZE:]

    def handle_packet(self, payload, errors, error_pos):
        print(f"Packet:{bytes(payload)}\n{errors} errors in positions {error_pos}")
        # TODO: Data should be passed forward to netwrok layer protocol 