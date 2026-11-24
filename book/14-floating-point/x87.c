#include <float.h>
#include <ieeefp.h>                      /* FreeBSD: fpgetprec, fpsetprec */
#include <stdio.h>

int main(void)
{
    printf("LDBL_MANT_DIG = %d, x87 precision control = %d (FP_PS %d, FP_PD %d, FP_PE %d)\n",
           LDBL_MANT_DIG, (int)fpgetprec(), FP_PS, FP_PD, FP_PE);

    volatile double a = 1.0, b = 0x1p-53 + 0x1p-78;     /* exact sum: 1 + 2^-53 + 2^-78 */
    double once = a + b;                                /* SSE2: one rounding to 53 bits */
    volatile long double wide = (long double)a + b;     /* x87: rounded to 64 bits ... */
    double twice = (double)wide;                        /* ... then to 53 bits */
    printf("one rounding:  1 + %g ulp\n", (once - 1) / DBL_EPSILON);
    printf("two roundings: 1 + %g ulp\n", (twice - 1) / DBL_EPSILON);

    fpsetprec(FP_PD);                                   /* x87 rounds significands to 53 bits */
    volatile long double pd = (long double)a + b;
    volatile long double big = DBL_MAX;
    long double bigger = big * 2;
    fpsetprec(FP_PE);
    printf("PC = 53 bits:  1 + %g ulp\n", (double)((pd - 1) / DBL_EPSILON));
    printf("PC = 53 bits:  DBL_MAX * 2 = %Lg in a register, %g stored as double\n",
           bigger, (double)bigger);
    return 0;
}
