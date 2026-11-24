#include <math.h>
#include <stdint.h>
#include <stdio.h>

static uint64_t st = 99;
static double gauss(void)                /* Box-Muller: mean 0, variance 1 */
{
    st = st * 6364136223846793005u + 1442695040888963407u;
    double u1 = ((st >> 11) + 1.0) / 9007199254740993.0;
    st = st * 6364136223846793005u + 1442695040888963407u;
    double u2 = (st >> 11) / 9007199254740992.0;
    return sqrt(-2 * log(u1)) * cos(6.283185307179586 * u2);
}

int main(void)
{
    enum { N = 1024, T = 200 };
    int ds[4] = { 16, 64, 128, 256 };
    for (int t = 0; t < 4; t++) {
        int d = ds[t];
        double var = 0, maxw[2] = { 0, 0 }, eff[2] = { 0, 0 };
        for (int trial = 0; trial < T; trial++) {
            double q[256], s[N];
            for (int j = 0; j < d; j++) q[j] = gauss();
            for (int i = 0; i < N; i++) {
                s[i] = 0;
                for (int j = 0; j < d; j++) s[i] += q[j] * gauss();     /* q.k_i */
                var += s[i] * s[i] / ((double)N * T);
            }
            for (int sc = 0; sc < 2; sc++) {           /* 0: raw q.k, 1: q.k / sqrt(d) */
                double c = sc ? 1 / sqrt(d) : 1, m = -INFINITY, l = 0, l2 = 0;
                for (int i = 0; i < N; i++) m = fmax(m, c * s[i]);
                for (int i = 0; i < N; i++) { double e = exp(c * s[i] - m); l += e; l2 += e * e; }
                maxw[sc] += 1 / l / T;                  /* the largest weight is 1/l */
                eff[sc] += l * l / l2 / T;              /* 1 / sum(alpha_i^2) */
            }
        }
        printf("d = %3d: var(q.k) = %6.1f | raw: max weight %.2f, eff. keys %5.1f"
               " | scaled: max weight %.3f, eff. keys %5.1f\n",
               d, var, maxw[0], eff[0], maxw[1], eff[1]);
    }
    return 0;
}
