#include <stdio.h>
#include <stdlib.h>
#include <time.h>

#define D 128                               /* head dimension d */

/* s = K q: one decode step's logits (before the 1/sqrt(d)) for N cached keys */
static void kq(const float *K, const float *q, float *s, long n)
{
    for (long i = 0; i < n; i++) {
        float acc[8] = { 0 };               /* 8 independent sums: no add waits for the last */
        for (int j = 0; j < D; j += 8)
            for (int u = 0; u < 8; u++) acc[u] += K[i*D + j + u] * q[j + u];
        s[i] = ((acc[0] + acc[1]) + (acc[2] + acc[3]))
             + ((acc[4] + acc[5]) + (acc[6] + acc[7]));
    }
}

static void bench(long n, int reps)
{
    float *K = malloc(sizeof *K * n * D), *s = malloc(sizeof *s * n), q[D];
    for (long i = 0; i < n * D; i++) K[i] = rand() / (float)RAND_MAX - 0.5f;
    for (int j = 0; j < D; j++) q[j] = rand() / (float)RAND_MAX - 0.5f;
    kq(K, q, s, n);                         /* warm up: page in, fill caches */
    clock_t t0 = clock();
    for (int r = 0; r < reps; r++) { q[r % D] += 1e-3f; kq(K, q, s, n); }
    double t = (double)(clock() - t0) / CLOCKS_PER_SEC / reps;
    printf("N = %7ld (K is %6.1f MB): %8.1f us per K q  %5.2f GFLOP/s  %5.1f GB/s read"
           "  (s[0] %.3f)\n",
           n, n * D * 4 / 1e6, t * 1e6, 2.0 * n * D / t / 1e9, n * D * 4.0 / t / 1e9, s[0]);
    free(K); free(s);
}

int main(void)
{
    bench(1024, 20000);                     /* 0.5 MB: stays in L2/L3 cache */
    bench(262144, 50);                      /* 128 MB: streamed from DRAM each time */
    return 0;
}
