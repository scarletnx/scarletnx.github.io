#include <math.h>
#include <stdio.h>

static void softmax(const float *s, float *w, int n)
{
    float m = s[0], sum = 0;
    for (int i = 1; i < n; i++) if (s[i] > m) m = s[i];
    for (int i = 0; i < n; i++) sum += w[i] = expf(s[i] - m);   /* every term in (0, 1] */
    for (int i = 0; i < n; i++) w[i] /= sum;
}

int main(void)
{
    float tests[4][3] = { { 1, 2, 3 }, { 100, 101, 102 }, { -200, -201, -202 },
                          { 1000, 0, -1000 } };
    for (int t = 0; t < 4; t++) {
        float w[3];
        softmax(tests[t], w, 3);
        printf("s = (%g, %g, %g)  ->  w = (%.7f, %.7f, %.7f)\n", tests[t][0], tests[t][1],
               tests[t][2], w[0], w[1], w[2]);
    }
    return 0;
}
