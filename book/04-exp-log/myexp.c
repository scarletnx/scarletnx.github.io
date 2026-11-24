#include <math.h>
#include <stdio.h>

static const double LN2_HI = 6.93147180369123816490e-01;  /* low 32 bits zero: k*LN2_HI is exact */
static const double LN2_LO = 1.90821492927058770002e-10;  /* ln 2 - LN2_HI */
static const double LOG2E  = 1.44269504088896338700e+00;

static double my_exp(double x)                /* for |x| <= 700 */
{
    double k = nearbyint(x * LOG2E);          /* x = k ln 2 + r */
    double r = (x - k * LN2_HI) - k * LN2_LO; /* |r| <= ln2/2, about 0.347 */
    double p = 1;                             /* 1 + r(1 + r/2(1 + r/3(... (1 + r/13)))) */
    for (int n = 13; n >= 1; n--)
        p = 1 + p * r / n;
    return ldexp(p, (int)k);                  /* times 2^k: add k to the exponent */
}

static double ulps(double y, long double ref)  /* error in units of the last place */
{
    return (double)(fabsl(y - ref) / ldexpl(1, ilogbl(ref) - 52));
}

int main(void)
{
    double mine = 0, lib = 0, at = 0;
    for (long i = 0; i <= 14000000; i++) {
        double x = -700 + i * 1e-4 + 1e-9 * (i % 7);
        long double ref = expl(x);            /* 64-bit significand reference */
        double e1 = ulps(my_exp(x), ref), e2 = ulps(exp(x), ref);
        if (e1 > mine) { mine = e1; at = x; }
        if (e2 > lib) lib = e2;
    }
    printf("my_exp: max error %.3f ulp (at x = %.4f)\n", mine, at);
    printf("libm  : max error %.3f ulp\n", lib);
    printf("my_exp(1) = %.17g\nexp(1)    = %.17g\n", my_exp(1), exp(1));
    return 0;
}
