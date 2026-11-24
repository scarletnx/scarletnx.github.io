#include <math.h>
#include <stdio.h>

int main(void)
{
    float xs[] = { 1.0f, 1000.0f, 16777216.0f };       /* 16777216 = 2^24 */
    for (int i = 0; i < 3; i++)
        printf("ulp(%.0f) = %g\n", xs[i], nextafterf(xs[i], INFINITY) - xs[i]);

    /* integers between 2^24 and 2^25 are 2 apart in float: odd ones are ties */
    for (long n = 16777217; n <= 16777223; n += 2)
        printf("%ld -> %.0f\n", n, (float)n);

    printf("0.1f is exactly %.30f\n", 0.1f);
    printf("0.1f - 0.1 = %.3g  (half an ulp of 0.1f is %.3g)\n",
           (double)0.1f - 0.1, (nextafterf(0.1f, 1) - 0.1f) / 2.0);
    return 0;
}
