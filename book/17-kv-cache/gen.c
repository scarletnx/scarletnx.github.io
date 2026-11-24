/* A toy autoregressive loop: one attention head, d = 8. Each step's input is
   built from the previous step's output. Run it twice: recomputing every key
   and value each step, and keeping them in a cache. Same outputs, less work. */
#include <math.h>
#include <stdio.h>

#define D 8
#define T 64

static double Wq[D][D], Wk[D][D], Wv[D][D];
static long macs;                               /* multiply-adds done */

static void matvec(double W[D][D], const double *x, double *y)
{
    for (int i = 0; i < D; i++) {
        y[i] = 0;
        for (int j = 0; j < D; j++) y[i] += W[i][j] * x[j];
    }
    macs += D * D;
}

/* attend: q against n keys/values, output o */
static void attend(const double *q, double K[][D], double V[][D], int n, double *o)
{
    double s[T], m = -INFINITY, z = 0;
    for (int i = 0; i < n; i++) {
        s[i] = 0;
        for (int j = 0; j < D; j++) s[i] += q[j] * K[i][j];
        s[i] /= sqrt(D);
        if (s[i] > m) m = s[i];
    }
    for (int j = 0; j < D; j++) o[j] = 0;
    for (int i = 0; i < n; i++) {
        double w = exp(s[i] - m);
        z += w;
        for (int j = 0; j < D; j++) o[j] += w * V[i][j];
    }
    for (int j = 0; j < D; j++) o[j] /= z;
    macs += 2L * n * D;
}

static double run(int use_cache)
{
    static double X[T][D], K[T][D], V[T][D];
    double q[D], o[D], check = 0;
    macs = 0;
    for (int j = 0; j < D; j++) X[0][j] = cos(j);      /* the prompt: one token */
    for (int t = 0; t < T; t++) {
        if (use_cache) {                               /* only the new token */
            matvec(Wk, X[t], K[t]);
            matvec(Wv, X[t], V[t]);
        } else {                                       /* all tokens again */
            for (int i = 0; i <= t; i++) {
                matvec(Wk, X[i], K[i]);
                matvec(Wv, X[i], V[i]);
            }
        }
        matvec(Wq, X[t], q);
        attend(q, K, V, t + 1, o);
        if (t + 1 < T)
            for (int j = 0; j < D; j++) X[t + 1][j] = tanh(o[j] + X[t][j]);
        check += o[0];
    }
    return check;
}

int main(void)
{
    for (int i = 0; i < D; i++)
        for (int j = 0; j < D; j++) {
            Wq[i][j] = sin(1.0 + i * D + j);
            Wk[i][j] = sin(2.0 + i * D + j);
            Wv[i][j] = sin(3.0 + i * D + j);
        }
    double a = run(0); long ma = macs;
    double b = run(1); long mb = macs;
    printf("no cache:   checksum %.15f   multiply-adds %ld\n", a, ma);
    printf("with cache: checksum %.15f   multiply-adds %ld\n", b, mb);
    return 0;
}
