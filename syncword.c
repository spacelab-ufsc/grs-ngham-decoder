#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include "syncword.h"

size_t count_ones_in_byte(uint8_t byte) {
    size_t count = 0;
    while (byte) {
        count += byte & 1;
        byte >>= 1;
    }
    return count;
}

SyncWord* syncword_create(uint8_t* bytes, size_t byte_count) {
    SyncWord* sw = malloc(sizeof(SyncWord));
    if (!sw) return NULL;

    sw->bytes = malloc(byte_count);
    if (!sw->bytes) {free (sw); return NULL;}
    memcpy(sw->bytes, bytes, byte_count);

    sw->byte_len = byte_count;

    return sw;
}

int syncword_detect(SyncWord* syncword, size_t max_errors, size_t size_byte_stream, uint8_t* byte_stream) {
    if (syncword->byte_len > size_byte_stream) {
        return -1;
    }

    int last_index = size_byte_stream - syncword->byte_len;

    for (size_t i = 0; i <= last_index; i++) {
        int dist = 0;
        for (size_t j = 0; j < syncword->byte_len; j++) {
            dist += count_ones_in_byte(syncword->bytes[j] ^ byte_stream[i+j]);
        }

        if (dist <= max_errors) {
            return i + syncword->byte_len;
        }
    }
    return -1;
}

void syncword_destroy(SyncWord* sw) {
    if (!sw) return;
    free(sw->bytes);
    free(sw);
}

