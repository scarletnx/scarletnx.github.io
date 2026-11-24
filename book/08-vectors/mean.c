#include <math.h>
#include <stdio.h>
#include <stdlib.h>

#define D 4          /* d: key dimension */
#define C 6          /* |C|: keys in the cluster */

static double dot(const double *a, const double *b)
{
    double s = 0;
    for (int j = 0; j < D; j++)
        s += a[j] * b[j];
    return s;
}

int main(void)
{
    double k[C][D], kbar[D] = { 0 }, r[C][D], rsum[D] = { 0 }, q[D];
    srand(8);
    for (int i = 0; i < C; i++)
        for (int j = 0; j < D; j++)
            k[i][j] = 2.0 * rand() / RAND_MAX - 1;
    for (int j = 0; j < D; j++)
        q[j] = 4.0 * rand() / RAND_MAX - 2;

    for (int i = 0; i < C; i++)                       /* kbar_C = (1/|C|) sum k_i */
        for (int j = 0; j < D; j++)
            kbar[j] += k[i][j] / C;
    for (int i = 0; i < C; i++)                       /* r_i = k_i - kbar_C */
        for (int j = 0; j < D; j++)
            rsum[j] += r[i][j] = k[i][j] - kbar[j];

    double mean_logit = 0, delta = 0;
    for (int i = 0; i < C; i++) {
        double s = dot(q, k[i]), dev = dot(q, r[i]);
        mean_logit += s / C;
        printf("i=%d  q.k_i = %8.5f   q.kbar + q.r_i = %8.5f   q.r_i = %8.5f\n",
               i, s, dot(q, kbar) + dev, dev);
        if (fabs(dev) / sqrt(D) > delta) delta = fabs(dev) / sqrt(D);
    }
    printf("q.kbar = %.17g\nmean of q.k_i = %.17g\n", dot(q, kbar), mean_logit);
    printf("sum of r_i = (%.1e, %.1e, %.1e, %.1e)\n", rsum[0], rsum[1], rsum[2], rsum[3]);
    printf("delta_C = max |q.r_i| / sqrt(d) = %.5f\n", delta);
    double se = 0;
    for (int i = 0; i < C; i++) se += exp(dot(q, k[i]) / sqrt(D));
    printf("|C| exp(q.kbar/sqrt d) = %.5f  <=  sum exp(q.k_i/sqrt d) = %.5f\n",
           C * exp(dot(q, kbar) / sqrt(D)), se);
    printf("ratio %.5f  <=  cosh(delta_C) = %.5f\n",
           se / (C * exp(dot(q, kbar) / sqrt(D))), cosh(delta));
    return 0;
}
