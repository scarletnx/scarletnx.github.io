/* lemmas.c: Lemmas A.2 and A.3 of RefineKV, and the logits that make them tight. */
#include <math.h>
#include <stdio.h>

#define N 100000

/* m = mean of e^{x_i}; tv = sum |w_i - 1/n|, w = softmax(x) */
static void stats(const double *x, int n, double *m, double *tv)
{
    double z = 0;
    *m = 0; *tv = 0;
    for (int i = 0; i < n; i++) z += exp(x[i]);
    *m = z / n;
    for (int i = 0; i < n; i++) *tv += fabs(exp(x[i]) / z - 1.0 / n);
}

int main(void)
{
    static double x[N];
    double ds[] = { 0.1, 0.5, 1, 2, 4, 8 }, m, tv;
    printf("delta   cosh   m(half +-d)  2tanh(d/2)  tv(two-point)  tv(+-d halves)\n");
    for (int k = 0; k < 6; k++) {
        double d = ds[k];
        for (int i = 0; i < N; i++) x[i] = i < N / 2 ? d : -d;      /* mean 0 */
        stats(x, N, &m, &tv);
        double tvh = tv, mh = m;
        int f = (int)lround(N / (1 + exp(d)));                       /* share at +d */
        for (int i = 0; i < N; i++) x[i] = i < f ? d : -d;
        stats(x, N, &m, &tv);
        printf("%5.1f %9.4f %9.4f %11.4f %12.4f %14.4f\n", d, cosh(d), mh, 2 * tanh(d / 2), tv, tvh);
    }
    return 0;
}
