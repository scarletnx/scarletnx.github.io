#include <math.h>
#include <stdio.h>
#include <stdlib.h>

static double gauss(void)                 /* Box-Muller: one standard normal sample */
{
    double u = (rand() + 1.0) / (RAND_MAX + 2.0), v = (rand() + 1.0) / (RAND_MAX + 2.0);
    return sqrt(-2 * log(u)) * cos(6.283185307179586 * v);
}

int main(void)
{
    static double a[1024], b[1024];
    const int trials = 20000;
    srand(1);
    for (int d = 2; d <= 1024; d *= 8) {
        double sd = 0, sc = 0;
        for (int t = 0; t < trials; t++) {
            double ab = 0, aa = 0, bb = 0;
            for (int j = 0; j < d; j++) {
                a[j] = gauss(); b[j] = gauss();
                ab += a[j] * b[j]; aa += a[j] * a[j]; bb += b[j] * b[j];
            }
            sd += ab * ab;                    /* mean of (a.b)^2 estimates its variance */
            sc += fabs(ab) / sqrt(aa * bb);   /* |cos theta| */
        }
        printf("d = %4d: rms a.b = %6.3f  sqrt(d) = %6.3f   "
               "mean |cos| = %.4f  sqrt(2/(pi d)) = %.4f\n",
               d, sqrt(sd / trials), sqrt(d), sc / trials, sqrt(2 / (3.141592653589793 * d)));
    }
    return 0;
}
