#include <math.h>
#include <stdio.h>

int main(void)
{
    /* 1/a: Newton on f(x) = 1/x - a gives x <- x (2 - a x) */
    double a = 3.7;
    double x = (1 / a) * (1 - 0x1p-12);        /* a guess good to 12 bits, like rcpps */
    for (int n = 0; n <= 4; n++) {
        printf("1/a  step %d: %.17f  rel err %.1e\n", n, x, fabs(x * a - 1));
        x = x * (2 - a * x);
    }

    /* cos x = x: Newton on f(x) = cos x - x, f'(x) = -sin x - 1 */
    double y = 1;
    for (int n = 1; n <= 5; n++) {
        y = y - (cos(y) - y) / (-sin(y) - 1);
        printf("cos x = x  step %d: %.17f  f = %.1e\n", n, y, cos(y) - y);
    }
    return 0;
}
