#ifndef SYNCWORD_H
#define SYNCWORD_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

/**
 * Represents a sync word 
 */
typedef struct {
    uint8_t*  bytes;
    size_t byte_len;
} SyncWord;

/**
 * Create a SyncWord from a byte array.
 *
 * @param bytes      Raw sync word bytes
 * @param byte_count Number of bytes
 * @return           Heap-allocated SyncWord, or NULL on allocation failure
 */
SyncWord* syncword_create(uint8_t* bytes, size_t byte_count);

/**
 * Search for a sync word in a bit stream.
 *
 * @param byte_stream      Incoming byte stream
 * @param syncword         The sync word to search for
 * @param max_errors       Maximum bit mismatches to tolerate
 * @param size_byte_stream Length of byte stream
 * @return                 Index of first byte after the sync word,
 *                         or -1 if not found
 */
int syncword_detect(SyncWord* syncword,size_t max_errors,
                    size_t size_byte_stream, uint8_t* byte_stream);

/**
 * Free a SyncWord created by syncword_create.
 */
void syncword_destroy(SyncWord* sw);

#endif /* SYNCWORD_H */