#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

static void show(float x)
{
    uint32_t b;
    memcpy(&b, &x, sizeof b);              /* the bits, without breaking aliasing rules */
    unsigned s = b >> 31, e = (b >> 23) & 0xff, f = b & 0x7fffff;
    double val = ldexp(1.0 + f / 8388608.0, (int)e - 127) * (s ? -1 : 1);
    printf("%-10g bits %08x  sign %u  exp %3u (2^%-4d)  frac 0x%06x  -> %.10g\n",
           x, (unsigned)b, s, e, (int)e - 127, f, val);
}

int main(void)
{
    show(1.0f); show(-6.5f); show(0.1f); show(65504.0f);
    /* fields: name, exponent bits, fraction bits */
    struct { const char *name; int ebits, p; } fmt[] = {
        { "fp64", 11, 52 }, { "fp32", 8, 23 }, { "fp16", 5, 10 }, { "bf16", 8, 7 } };
    printf("\nformat bits  exp frac  bias  max          min normal   eps (2^-p)\n");
    for (int i = 0; i < 4; i++) {
        int bias = (1 << (fmt[i].ebits - 1)) - 1;
        printf("%-6s %4d %4d %4d %5d  %-12.5g %-12.5g %.5g\n", fmt[i].name,
               1 + fmt[i].ebits + fmt[i].p, fmt[i].ebits, fmt[i].p, bias,
               ldexp(2 - ldexp(1, -fmt[i].p), bias), ldexp(1, 1 - bias), ldexp(1, -fmt[i].p));
    }
    return 0;
}
