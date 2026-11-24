#include <math.h>
#include <stdint.h>
#include <stdio.h>

static uint64_t st = 88172645463325252u;
static float rnd(void)                   /* xorshift64: a float in about [-1000, 1000] */
{
    st ^= st << 13; st ^= st >> 7; st ^= st << 17;
    return (float)((double)(st >> 11) / 9007199254740992.0 * 2000.0 - 1000.0);
}

int main(void)
{
    const long double u = 0x1p-24L;      /* unit roundoff of float */
    long double worst[4] = { 0, 0, 0, 0 };
    const char *name[4] = { "a + b", "a * b", "a / b", "sqrt(|a|)" };
    for (int t = 0; t < 10000000; t++) {
        float a = rnd(), b = rnd();
        float got[4] = { a + b, a * b, a / b, sqrtf(fabsf(a)) };
        long double a1 = a, b1 = b;      /* 64-bit significand: + and * of these are exact */
        long double ex[4] = { a1 + b1, a1 * b1, a1 / b1, sqrtl(fabsl(a1)) };
        for (int k = 0; k < 4; k++) {
            if (ex[k] == 0) continue;
            long double eps = fabsl((got[k] - ex[k]) / ex[k]);
            if (eps > worst[k]) worst[k] = eps;
        }
    }
    for (int k = 0; k < 4; k++)
        printf("%-10s max |eps| = %.6Lf u\n", name[k], worst[k] / u);
    return 0;
}
