#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

static float pairwise(const float *x, long n)
{
    if (n <= 8) {
        float s = 0;
        for (long i = 0; i < n; i++) s += x[i];
        return s;
    }
    return pairwise(x, n / 2) + pairwise(x + n / 2, n - n / 2);
}

static float kahan(const float *x, long n)
{
    float s = 0, c = 0;                  /* c holds the low bits lost so far, negated */
    for (long i = 0; i < n; i++) {
        float y = x[i] - c;
        float t = s + y;
        c = (t - s) - y;                 /* what of y did not make it into t */
        s = t;
    }
    return s;
}

int main(void)
{
    const long n = 10000000;
    float *x = malloc(n * sizeof *x);
    uint64_t st = 1;
    double ref = 0;                      /* double: exact enough to judge float */
    for (long i = 0; i < n; i++) {
        st = st * 6364136223846793005u + 1442695040888963407u;
        x[i] = (float)(st >> 40) / 16777216.0f;          /* uniform in [0, 1) */
        ref += x[i];
    }
    float naive = 0;
    for (long i = 0; i < n; i++) naive += x[i];
    float p = pairwise(x, n), k = kahan(x, n);
    printf("exact    %.1f\n", ref);
    printf("naive    %.1f  rel err %.1e\n", naive, fabs(naive - ref) / ref);
    printf("pairwise %.1f  rel err %.1e\n", p, fabs(p - ref) / ref);
    printf("kahan    %.1f  rel err %.1e\n", k, fabs(k - ref) / ref);
    printf("bounds: n*u = %.1e, log2(n)*u = %.1e, 2u = %.1e\n",
           n * 0x1p-24, log2((double)n) * 0x1p-24, 2 * 0x1p-24);

    float ones = 0;
    for (long i = 0; i < 20000000; i++) ones += 1.0f;
    printf("1.0f added 20000000 times = %.0f\n", ones);
    free(x);
    return 0;
}
