#include <float.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

static uint32_t bits(float x) { uint32_t b; memcpy(&b, &x, 4); return b; }
static float from(uint32_t b) { float x; memcpy(&x, &b, 4); return x; }

/* bf16 is the top 16 bits of a float. (NaN inputs are not handled here.) */
static uint16_t bf16_trunc(float x) { return (uint16_t)(bits(x) >> 16); }
static uint16_t bf16_round(float x)  /* round to nearest, ties to even */
{
    uint32_t b = bits(x);
    b += 0x7fff + ((b >> 16) & 1);   /* add just under half, plus 1 if the kept part is odd */
    return (uint16_t)(b >> 16);
}
static float bf16_to_float(uint16_t h) { return from((uint32_t)h << 16); }

int main(void)
{
    float xs[] = { 1.0f / 3, 3.14159265f, 1.00390625f, 300.5f, 65504.0f };
    for (int i = 0; i < 5; i++)
        printf("%-11.9g bf16 truncated %-9.6g rounded %-9.6g  fp16 %.9g\n", xs[i],
               bf16_to_float(bf16_trunc(xs[i])), bf16_to_float(bf16_round(xs[i])),
               (double)(_Float16)xs[i]);
    printf("fp16: 65519 -> %g, 65520 -> %g, 1e-8 -> %g, 2^-24 -> %g\n",
           (double)(_Float16)65519.0f, (double)(_Float16)65520.0f,
           (double)(_Float16)1e-8f, (double)(_Float16)0x1p-24f);
    printf("bf16: 1e38 -> %g, 1e-38 -> %g\n",
           bf16_to_float(bf16_round(1e38f)), bf16_to_float(bf16_round(1e-38f)));
    volatile float a = 88.72f, b = 88.73f;
    printf("ln(FLT_MAX) = %.4f: expf(88.72) = %g, expf(88.73) = %g\n",
           log(FLT_MAX), expf(a), expf(b));
    printf("ln(65504) = %.4f: exp(11.09) = %.1f, exp(11.10) = %.1f\n",
           log(65504.0), exp(11.09), exp(11.10));
    return 0;
}
