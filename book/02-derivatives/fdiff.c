#include <float.h>
#include <math.h>
#include <stdio.h>

int main(void)
{
    for (int k = 1; k <= 15; k++) {
        double h = pow(10, -k), ef = 0, ec = 0;
        for (int j = 0; j < 1000; j++) {       /* average over x in [0.5, 1.5) */
            double x = 0.5 + j / 1000.0, exact = exp(x);   /* (e^x)' = e^x */
            double fwd = (exp(x + h) - exp(x)) / h;
            double cen = (exp(x + h) - exp(x - h)) / (2 * h);
            ef += fabs(fwd - exact) / exact / 1000;
            ec += fabs(cen - exact) / exact / 1000;
        }
        printf("h = 1e-%02d  forward err %.1e  central err %.1e\n", k, ef, ec);
    }
    printf("sqrt(eps) = %.1e   cbrt(eps) = %.1e\n", sqrt(DBL_EPSILON), cbrt(DBL_EPSILON));
    return 0;
}
