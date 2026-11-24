#include <math.h>
#include <stdio.h>

enum { D = 8 };

static void rope(const double *x, double *y, int pos)   /* rotate pair j by pos * theta_j */
{
    for (int j = 0; j < D / 2; j++) {
        double th = pos * pow(10000.0, -2.0 * j / D), c = cos(th), s = sin(th);
        y[2 * j]     = c * x[2 * j] - s * x[2 * j + 1];
        y[2 * j + 1] = s * x[2 * j] + c * x[2 * j + 1];
    }
}

static double dot(const double *a, const double *b)
{
    double s = 0;
    for (int j = 0; j < D; j++) s += a[j] * b[j];
    return s;
}

int main(void)
{
    double q[D] = { 1, 2, -1, 0.5, 3, -2, 0.1, 1 }, k[D] = { 0.3, -1, 2, 1, -0.5, 1, 2, -1 };
    int pos[4][2] = { { 5, 2 }, { 103, 100 }, { 1003, 1000 }, { 7, 2 } };
    for (int t = 0; t < 4; t++) {
        double rq[D], rk[D];
        rope(q, rq, pos[t][0]);                 /* the query at position m */
        rope(k, rk, pos[t][1]);                 /* the key at position n */
        printf("m = %4d, n = %4d, m - n = %d: q.k = %.6f, |Rq| = %.6f\n",
               pos[t][0], pos[t][1], pos[t][0] - pos[t][1], dot(rq, rk), sqrt(dot(rq, rq)));
    }
    printf("without rotation: q.k = %.6f, |q| = %.6f\n", dot(q, k), sqrt(dot(q, q)));
    return 0;
}
