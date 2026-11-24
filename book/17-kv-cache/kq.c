/* Time s = K q for 2^20 keys of d = 128 floats (512 MiB, far beyond any CPU
   cache), then for B queries at once: the keys read once, used B times.
   Keys are stored in tiles of 32 (tile[j][l] = key l, coordinate j) so the
   inner loop runs across keys, 4 floats per SSE instruction. One core. */
#define _POSIX_C_SOURCE 199309L                /* clock_gettime, in glibc too */
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

#define D 128
#define N (1L << 20)
#define TL 32

static double now(void)
{
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return t.tv_sec + 1e-9 * t.tv_nsec;
}

int main(void)
{
    float *K = malloc(sizeof(float) * N * D);
    float *Q = malloc(sizeof(float) * 64 * D);
    float *s = malloc(sizeof(float) * N * 64);
    if (!K || !Q || !s) return 1;
    for (long i = 0; i < N * D; i++) K[i] = (float)((i * 2654435761u) % 1000) / 1000 - 0.5f;
    for (long i = 0; i < 64 * D; i++) Q[i] = (float)(i % 7) / 7 - 0.5f;

    double best = 1e9, sum = 0;                     /* first: just read K */
    for (int rep = 0; rep < 5; rep++) {
        float acc[TL] = { 0 };
        double t0 = now();
        for (long i = 0; i < N * D; i += TL)
            for (int l = 0; l < TL; l++) acc[l] += K[i + l];
        double dt = now() - t0;
        if (dt < best) best = dt;
        for (int l = 0; l < TL; l++) sum += acc[l];
    }
    printf("read only: %6.1f ms  %5.1f GB/s  (sum %g)\n", best * 1e3,
           sizeof(float) * (double)N * D / best / 1e9, sum);

    int bs[] = { 1, 2, 4, 16, 64 };
    for (int t = 0; t < 5; t++) {
        int B = bs[t];
        best = 1e9;
        for (int rep = 0; rep < 5; rep++) {
            double t0 = now();
            for (long i0 = 0; i0 < N; i0 += TL) {
                const float *tile = K + i0 * D;            /* D rows of TL keys */
                for (int b = 0; b < B; b++) {
                    const float *q = Q + b * D;
                    float acc[TL] = { 0 };
                    for (int j = 0; j < D; j++)
                        for (int l = 0; l < TL; l++) acc[l] += q[j] * tile[j * TL + l];
                    for (int l = 0; l < TL; l++) s[(i0 + l) * B + b] = acc[l];
                }
            }
            double dt = now() - t0;
            if (dt < best) best = dt;
        }
        double bytes = (double)N * D * sizeof(float), flops = 2.0 * N * D * B;
        printf("B = %2d:    %7.1f ms  %5.1f GB/s of keys  %5.1f GFLOP/s  (%4.1f FLOP/byte)\n",
               B, best * 1e3, bytes / best / 1e9, flops / best / 1e9, flops / bytes);
    }
    printf("check %f\n", s[12345]);
    free(K); free(Q); free(s);
    return 0;
}
