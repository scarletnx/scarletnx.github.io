#include <math.h>
#include <stdio.h>

int main(void)
{
    for (int k = 1; k <= 9; k++) {
        double x = pow(10, -k);
        double naive = (1 - cos(x)) / (x * x);
        double s = sin(x / 2);
        double stable = 2 * s * s / (x * x);   /* 1 - cos x = 2 sin^2(x/2) */
        printf("x = 1e-%d   naive %.10f   stable %.10f\n", k, naive, stable);
    }
    return 0;
}
