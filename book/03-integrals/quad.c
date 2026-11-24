#include <math.h>
#include <stdio.h>

int main(void)
{
    double exact = exp(1) - 1, et_old = 0, es_old = 0;   /* int_0^1 e^x dx */
    for (int n = 2; n <= 512; n *= 2) {
        double h = 1.0 / n, t = (exp(0) + exp(1)) / 2, s = exp(0) + exp(1);
        for (int i = 1; i < n; i++) {
            t += exp(i * h);
            s += exp(i * h) * (i % 2 ? 4 : 2);
        }
        double et = fabs(t * h - exact), es = fabs(s * h / 3 - exact);
        printf("n = %3d  trapezoid err %.3e", n, et);
        if (n > 2) printf(" (ratio %5.2f)", et_old / et); else printf("              ");
        printf("  Simpson err %.3e", es);
        if (n > 2) printf(" (ratio %5.2f)", es_old / es);
        printf("\n");
        et_old = et; es_old = es;
    }
    return 0;
}
