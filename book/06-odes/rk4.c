#include <math.h>
#include <stdio.h>

/* Euler and RK4 on the logistic equation y' = y (1 - y), y(0) = 0.1, up to t = 5.
   Exact solution 1 / (1 + 9 e^-t). */
static double f(double t, double y) { (void)t; return y * (1 - y); }

static double euler(double h, int n)
{
    double t = 0, y = 0.1;
    for (int i = 0; i < n; i++, t += h)
        y += h * f(t, y);
    return y;
}

static double rk4(double h, int n)
{
    double t = 0, y = 0.1;
    for (int i = 0; i < n; i++, t += h) {
        double k1 = f(t, y);
        double k2 = f(t + h / 2, y + h / 2 * k1);
        double k3 = f(t + h / 2, y + h / 2 * k2);
        double k4 = f(t + h, y + h * k3);
        y += h / 6 * (k1 + 2 * k2 + 2 * k3 + k4);
    }
    return y;
}

int main(void)
{
    double exact = 1 / (1 + 9 * exp(-5)), pe = 0, pr = 0;
    printf("   h     Euler error  ratio   RK4 error   ratio   f evals (RK4)\n");
    for (int n = 10; n <= 640; n *= 2) {
        double h = 5.0 / n;
        double ee = fabs(euler(h, n) - exact), er = fabs(rk4(h, n) - exact);
        if (pe)
            printf("%.5f  %.3e  %5.2f   %.3e  %5.2f   %d\n", h, ee, pe / ee, er, pr / er, 4 * n);
        else
            printf("%.5f  %.3e          %.3e          %d\n", h, ee, er, 4 * n);
        pe = ee;
        pr = er;
    }
    return 0;
}
