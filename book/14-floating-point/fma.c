#include <float.h>
#include <math.h>
#include <stdio.h>

int main(void)
{
    volatile float a = 1.0f + 0x1p-12f;  /* volatile: computed at run time */
    float p = a * a;                     /* exact: 1 + 2^-11 + 2^-24; rounded */
    float lost = a * a - p;              /* rounded again: the low bit is gone */
    float err = fmaf(a, a, -p);          /* a*a - p with one rounding: exact */
    printf("a*a     = %.10f\n", p);
    printf("a*a - p = %g without fma, %g with fma (2^-24 = %g)\n", lost, err, 0x1p-24);
    return 0;
}
