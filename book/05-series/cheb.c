#include <math.h>
#include <stdio.h>

#define A 0.34657359027997264L   /* ln2/2: exp(r) is needed on [-A, A] */

static double horner(const double *c, int n, double r)
{
    double p = c[n];
    for (int k = n - 1; k >= 0; k--)
        p = fma(p, r, c[k]);
    return p;
}

/* The degree-n polynomial equal to exp at the n+1 Chebyshev points of [-A, A],
   in powers of r. Long double keeps the fit's own rounding below 2^-53. */
static void cheb_fit(int n, double *c)
{
    long double t[16][16] = { { 0 } }, a[16], pi = 3.14159265358979323846L;
    t[0][0] = 1; t[1][1] = 1;                 /* t[k][i]: coefficient of u^i in T_k(u) */
    for (int k = 2; k <= n; k++)              /* T_k = 2u T_(k-1) - T_(k-2) */
        for (int i = 0; i <= k; i++)
            t[k][i] = (i ? 2 * t[k - 1][i - 1] : 0) - t[k - 2][i];
    for (int k = 0; k <= n; k++) {            /* a_k = 2/(n+1) sum_j f(u_j) T_k(u_j) */
        a[k] = 0;
        for (int j = 0; j <= n; j++) {
            long double th = pi * (j + 0.5L) / (n + 1);
            a[k] += expl(A * cosl(th)) * cosl(k * th) * 2 / (n + 1);
        }
    }
    a[0] /= 2;
    for (int i = 0; i <= n; i++) {            /* sum_k a_k T_k(r/A), in powers of r */
        long double ci = 0;
        for (int k = i; k <= n; k++) ci += a[k] * t[k][i];
        c[i] = (double)(ci / powl(A, i));
    }
}

static double max_rel_err(const double *c, int n)
{
    double worst = 0;
    for (int i = 0; i <= 100000; i++) {
        double r = (double)(-A + 2 * A * i / 100000);
        double e = (double)fabsl((horner(c, n, r) - expl(r)) / expl(r));
        if (e > worst) worst = e;
    }
    return worst;
}

int main(void)
{
    double tay[16] = { 1 }, ch[16];
    printf("degree  Taylor      Chebyshev   ratio\n");
    for (int n = 3; n <= 13; n++) {
        for (int k = 1; k <= n; k++) tay[k] = tay[k - 1] / k;   /* 1/k! */
        cheb_fit(n, ch);
        double et = max_rel_err(tay, n), ec = max_rel_err(ch, n);
        printf("%4d   %.2e    %.2e    %5.1f\n", n, et, ec, et / ec);
    }
    return 0;
}
