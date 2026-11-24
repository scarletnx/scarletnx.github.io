#include <math.h>
#include <stdio.h>

int main(void)
{
    /* the small root of x^2 - 2bx + c = 0 is b - sqrt(b^2 - c) = c / (b + sqrt(b^2 - c)) */
    float bs[] = { 10.0f, 100.0f, 1000.0f, 10000.0f };
    float c = 1.0f;
    for (int i = 0; i < 4; i++) {
        float b = bs[i];
        float r = sqrtf(b * b - c);
        float naive = b - r;
        float stable = c / (b + r);
        double exact = 1.0 / ((double)b + sqrt((double)b * b - 1.0));
        printf("b = %5.0f  naive %.7e (rel err %.1e)  stable %.7e (rel err %.1e)\n", b,
               naive, fabs(naive - exact) / exact, stable, fabs(stable - exact) / exact);
    }
    return 0;
}
