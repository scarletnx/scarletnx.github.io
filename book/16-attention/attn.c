#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

enum { HQ = 32, HKV = 8, D = 128, N = 4096 };   /* Llama-3.1-8B's head counts and head size */

static float bf16_to_f(uint16_t h) { uint32_t b = (uint32_t)h << 16; float x; memcpy(&x, &b, 4); return x; }
static uint16_t f_to_bf16(float x)
{
    uint32_t b; memcpy(&b, &x, 4);
    return (uint16_t)((b + 0x7fff + ((b >> 16) & 1)) >> 16);
}

/* one layer, one new token: q[HQ][D] against the cache K, V [HKV][N][D] (bf16) */
static void attend(const float *q, const uint16_t *K, const uint16_t *V, float *o)
{
    for (int h = 0; h < HQ; h++) {
        int g = h / (HQ / HKV);                 /* the KV head this query head shares */
        const float *qh = q + h * D;
        float m = -INFINITY, l = 0, a[D] = { 0 };
        for (int i = 0; i < N; i++) {
            const uint16_t *k = K + ((size_t)g * N + i) * D, *v = V + ((size_t)g * N + i) * D;
            float s = 0;
            for (int j = 0; j < D; j++) s += qh[j] * bf16_to_f(k[j]);   /* fp32 accumulation */
            s /= sqrtf(D);
            float mn = fmaxf(m, s), r = expf(m - mn), p = expf(s - mn);
            l = l * r + p;
            for (int j = 0; j < D; j++) a[j] = a[j] * r + p * bf16_to_f(v[j]);
            m = mn;
        }
        for (int j = 0; j < D; j++) o[h * D + j] = a[j] / l;
    }
}

int main(void)
{
    size_t n = (size_t)HKV * N * D;
    uint16_t *K = malloc(n * 2), *V = malloc(n * 2);
    static float q[HQ * D], o[HQ * D];
    for (size_t i = 0; i < n; i++) {
        K[i] = f_to_bf16((float)sin(0.7 * i));
        V[i] = f_to_bf16((float)cos(0.3 * i));
    }
    for (int i = 0; i < HQ * D; i++) q[i] = (float)(2 * sin(1.3 * i));
    attend(q, K, V, o);

    double err = 0;                             /* check: two passes in double */
    for (int h = 0; h < HQ; h++) {
        const uint16_t *Kg = K + (size_t)(h / (HQ / HKV)) * N * D, *Vg = V + (Kg - K);
        static double s[N];
        double m = -INFINITY, l = 0;
        for (int i = 0; i < N; i++) {
            s[i] = 0;
            for (int j = 0; j < D; j++) s[i] += (double)q[h * D + j] * bf16_to_f(Kg[i * D + j]);
            s[i] /= sqrt(D);
            m = fmax(m, s[i]);
        }
        for (int i = 0; i < N; i++) l += exp(s[i] - m);
        for (int j = 0; j < D; j++) {
            double a = 0;
            for (int i = 0; i < N; i++) a += exp(s[i] - m) * bf16_to_f(Vg[i * D + j]);
            err = fmax(err, fabs(a / l - o[h * D + j]));
        }
    }
    printf("max |o - reference| over %d heads x %d: %.1e\n", HQ, D, err);

    double flops = 4.0 * HQ * N * D;            /* q.k and p*v: 2 flops per multiply-add */
    double bytes = 2.0 * HKV * N * D * 2;       /* K and V, 2 bytes each */
    printf("per layer: %.3g flops, %.3g bytes of K/V, %.1f flops per byte\n",
           flops, bytes, flops / bytes);
    printf("with %d KV heads (no sharing): %.1f flops per byte\n", HQ, flops / (bytes * HQ / HKV));
    double tok = 2.0 * 32 * HKV * D * 2;        /* K and V, 32 layers, bf16 */
    printf("KV cache per token, 32 layers: %.0f bytes; at 131072 tokens: %.1f GiB\n",
           tok, tok * 131072 / (1 << 30));
    free(K); free(V);
    return 0;
}
