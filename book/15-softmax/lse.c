#include <math.h>
#include <stdio.h>

static double lse_naive(const double *s, int n)
{
    double sum = 0;
    for (int i = 0; i < n; i++) sum += exp(s[i]);
    return log(sum);
}

static double lse(const double *s, int n)        /* m + log sum exp(s_i - m) */
{
    double m = s[0], sum = 0;
    for (int i = 1; i < n; i++) if (s[i] > m) m = s[i];
    for (int i = 0; i < n; i++) sum += exp(s[i] - m);
    return m + log(sum);
}

static double lse1p(const double *s, int n)      /* m + log1p(sum over the others) */
{
    int k = 0;
    double rest = 0;
    for (int i = 1; i < n; i++) if (s[i] > s[k]) k = i;
    for (int i = 0; i < n; i++) if (i != k) rest += exp(s[i] - s[k]);
    return s[k] + log1p(rest);
}

int main(void)
{
    double a[3] = { 1, 2, 3 }, b[3] = { 1000, 999, 998 }, c[2] = { 0, -40 };
    printf("(1, 2, 3):        naive %.15g  stable %.15g\n", lse_naive(a, 3), lse(a, 3));
    printf("(1000, 999, 998): naive %g  stable %.15g\n", lse_naive(b, 3), lse(b, 3));
    printf("(0, -40):         stable %g  with log1p %g  (e^-40 = %g)\n",
           lse(c, 2), lse1p(c, 2), exp(-40.0));
    printf("bounds for (1000, 999, 998): max %g <= lse <= max + ln 3 = %.15g\n",
           1000.0, 1000 + log(3.0));
    printf("log-softmax of 998: %.15g, log of its weight: %.15g\n",
           998 - lse(b, 3), log(exp(-2.0) / (1 + exp(-1.0) + exp(-2.0))));
    return 0;
}
