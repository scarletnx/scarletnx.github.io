#include <math.h>
#include <stdio.h>

static void softmax_naive(const float *s, float *w, int n)
{
    float sum = 0;
    for (int i = 0; i < n; i++) sum += expf(s[i]);
    for (int i = 0; i < n; i++) w[i] = expf(s[i]) / sum;
}

int main(void)
{
    float tests[3][3] = { { 1, 2, 3 }, { 100, 101, 102 }, { -200, -201, -202 } };
    for (int t = 0; t < 3; t++) {
        float w[3];
        softmax_naive(tests[t], w, 3);
        printf("s = (%g, %g, %g)  ->  w = (%g, %g, %g)\n", tests[t][0], tests[t][1],
               tests[t][2], w[0], w[1], w[2]);
    }
    printf("expf(100) = %g, expf(-200) = %g\n", expf(100), expf(-200));
    return 0;
}
