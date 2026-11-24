#include <math.h>
#include <stdint.h>
#include <stdio.h>

static uint64_t st = 0x2545F4914F6CDD1DULL;
static double rnd(void)                       /* uniform in [0, 1) */
{
    st ^= st << 13; st ^= st >> 7; st ^= st << 17;
    return (st >> 11) * 0x1p-53;
}

int main(void)
{
    /* x_1..x_n in [-delta, delta] with mean 0: is mean(e^{x_i}) <= cosh(delta)? */
    double worst = 0, least = INFINITY;
    for (int t = 0; t < 200000; t++) {
        int n = 3 + (int)(rnd() * 29);
        double x[32], mean = 0, big = 0, delta = 3 * rnd() + 1e-3;
        for (int i = 0; i < n; i++) {
            x[i] = rnd() < 0.5 ? rnd() : -rnd() * rnd();   /* lopsided on purpose */
            mean += x[i] / n;
        }
        for (int i = 0; i < n; i++) {
            x[i] -= mean;
            if (fabs(x[i]) > big) big = fabs(x[i]);
        }
        double m = 0;
        for (int i = 0; i < n; i++)
            m += exp(x[i] * delta / big) / n;  /* rescaled: max |x_i| = delta */
        if (m / cosh(delta) > worst) worst = m / cosh(delta);
        if (m < least) least = m;
    }
    printf("largest mean(e^x) / cosh(delta) = %.9f\n", worst);
    printf("smallest mean(e^x)              = %.9f\n", least);

    double d = 1.5;                           /* half at -delta, half at +delta */
    printf("x = +-1.5: mean(e^x) = %.6f  cosh(1.5) = %.6f\n", (exp(d) + exp(-d)) / 2, cosh(d));
    return 0;
}
