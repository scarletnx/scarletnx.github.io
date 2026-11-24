#include <math.h>
#include <stdio.h>

#define N 4

static void softmax(const double *s, double T, double *w)   /* as written: no max trick */
{
    double z = 0;
    for (int i = 0; i < N; i++) z += exp(s[i] / T);
    for (int i = 0; i < N; i++) w[i] = exp(s[i] / T) / z;
}

int main(void)
{
    double s[N] = { 2.0, 1.0, 0.5, -1.0 }, w[N];
    double Ts[] = { 0.1, 0.5, 1, 2, 10, 100 };
    for (int t = 0; t < 6; t++) {
        softmax(s, Ts[t], w);
        printf("T = %-5g w = %.4f %.4f %.4f %.4f\n", Ts[t], w[0], w[1], w[2], w[3]);
    }
    double sh[N], w2[N], diff = 0;
    for (int i = 0; i < N; i++) sh[i] = s[i] - 3.7;       /* shift every logit */
    softmax(s, 1, w); softmax(sh, 1, w2);
    for (int i = 0; i < N; i++) if (fabs(w[i] - w2[i]) > diff) diff = fabs(w[i] - w2[i]);
    printf("shift by -3.7: max weight change %.3g\n", diff);
    for (int i = 0; i < N; i++) sh[i] = s[i] + 1000;
    softmax(sh, 1, w2);
    printf("shift by +1000: w = %g %g %g %g\n", w2[0], w2[1], w2[2], w2[3]);
    printf("ln(w0/w1) = %.12f, s0 - s1 = %g\n", log(w[0] / w[1]), s[0] - s[1]);
    return 0;
}
