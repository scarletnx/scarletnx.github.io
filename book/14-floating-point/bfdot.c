#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

static float bf16(float x)               /* round a float to the nearest bf16, kept in a float */
{
    uint32_t b;
    memcpy(&b, &x, 4);
    b += 0x7fff + ((b >> 16) & 1);
    b &= 0xffff0000u;
    memcpy(&x, &b, 4);
    return x;
}

static uint64_t st = 12345;
static float gauss(void)                 /* sum of 4 uniforms, roughly normal */
{
    double s = 0;
    for (int i = 0; i < 4; i++) {
        st = st * 6364136223846793005u + 1442695040888963407u;
        s += (double)(st >> 11) / 9007199254740992.0 - 0.5;
    }
    return (float)s;
}

int main(void)
{
    enum { D = 128, T = 10000 };
    double e_in = 0, e32 = 0, e16 = 0;
    for (int t = 0; t < T; t++) {
        float q[D], k[D];
        double exact = 0, exact_bf = 0, mag = 0;
        float acc32 = 0, acc16 = 0;
        for (int j = 0; j < D; j++) {
            q[j] = gauss(); k[j] = gauss();
            float qb = bf16(q[j]), kb = bf16(k[j]);
            exact += (double)q[j] * k[j];
            exact_bf += (double)qb * kb;
            mag += fabs((double)q[j] * k[j]);
            acc32 += qb * kb;                    /* product exact in float; fp32 add */
            acc16 = bf16(acc16 + qb * kb);       /* sum kept in bf16 */
        }
        e_in += fabs(exact_bf - exact) / mag;
        e32 += fabs(acc32 - exact_bf) / mag;
        e16 += fabs(acc16 - exact_bf) / mag;
    }
    printf("mean error / sum|q_j k_j|, d = %d:\n", D);
    printf("  rounding inputs to bf16   %.1e\n", e_in / T);
    printf("  fp32 accumulation         %.1e\n", e32 / T);
    printf("  bf16 accumulation         %.1e\n", e16 / T);
    return 0;
}
