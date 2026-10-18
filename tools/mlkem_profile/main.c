// Bare-metal harness: one ML-KEM-512 keygen, encaps and decaps (PQClean "clean"), for instruction-level
// profiling under emulation (profile.py). No OS, no printf: results land in `result` for the emulator to read.
#include <stdint.h>
#include <string.h>
#include "api.h"
#include "randombytes.h"

static uint32_t lcg = 12345;
int randombytes(uint8_t *out, size_t n) {           // deterministic: same run every time
    while (n--) { lcg = lcg * 1664525u + 1013904223u; *out++ = (uint8_t)(lcg >> 24); }
    return 0;
}

uint8_t pk[PQCLEAN_MLKEM512_CLEAN_CRYPTO_PUBLICKEYBYTES], sk[PQCLEAN_MLKEM512_CLEAN_CRYPTO_SECRETKEYBYTES];
uint8_t ct[PQCLEAN_MLKEM512_CLEAN_CRYPTO_CIPHERTEXTBYTES], k1[32], k2[32];
volatile uint32_t result;

void phase(uint32_t p) { result = p; }               // the profiler watches calls to phase()

__attribute__((noreturn)) void run(void) {
    phase(1); PQCLEAN_MLKEM512_CLEAN_crypto_kem_keypair(pk, sk);
    phase(2); PQCLEAN_MLKEM512_CLEAN_crypto_kem_enc(ct, k1, pk);
    phase(3); PQCLEAN_MLKEM512_CLEAN_crypto_kem_dec(k2, ct, sk);
    phase(memcmp(k1, k2, 32) == 0 ? 0xC0DE : 0xBAD);
    for (;;) __asm__ volatile("bkpt #0");
}
