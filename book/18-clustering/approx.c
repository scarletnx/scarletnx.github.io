/* Exact attention against attention over cluster representatives.
   4096 AR(1) keys and values (rho = 0.98; values shifted to mean 1), d = 64,
   blocks of 32. A cluster counts as one
   token with logit q.kbar_C/sqrt(d) + ln|C| and value vbar_C. Also a mixed
   version: the 8 clusters with the largest phat_C keep their exact tokens. */
#include <math.h>
#include <stdio.h>
#include <stdlib.h>

#define N 4096
#define D 64
#define B 32
#define M (N / B)
#define EXPAND 8

static double K[N][D], V[N][D], kb[M][D], vb[M][D];

static double gauss(void)
{
    double u = (rand() + 1.0) / (RAND_MAX + 2.0), v = (rand() + 1.0) / (RAND_MAX + 2.0);
    return sqrt(-2 * log(u)) * cos(6.283185307179586 * v);
}
static double dot(const double *a, const double *b)
{
    double s = 0;
    for (int j = 0; j < D; j++) s += a[j] * b[j];
    return s / sqrt(D);
}
/* softmax over n logits l[] with values from rows[]; output into o */
static void attend(int n, const double *l, const double **rows, double *o)
{
    double m = -INFINITY, z = 0;
    for (int i = 0; i < n; i++) if (l[i] > m) m = l[i];
    for (int j = 0; j < D; j++) o[j] = 0;
    for (int i = 0; i < n; i++) {
        double w = exp(l[i] - m);
        z += w;
        for (int j = 0; j < D; j++) o[j] += w * rows[i][j];
    }
    for (int j = 0; j < D; j++) o[j] /= z;
}
static double relerr(const double *o, const double *oh)
{
    double e = 0, n = 0;
    for (int j = 0; j < D; j++) { e += pow(oh[j] - o[j], 2); n += o[j] * o[j]; }
    return sqrt(e / n);
}

int main(void)
{
    static double l[N], lr[N];
    static const double *rows[N];
    double err[4] = { 0 };
    srand(6);
    for (int i = 0; i < N; i++)
        for (int j = 0; j < D; j++) {
            K[i][j] = (i ? 0.98 * K[i - 1][j] : 0) + sqrt(1 - 0.98 * 0.98) * gauss();
            V[i][j] = (i ? 0.98 * (V[i - 1][j] - 1) : 0) + sqrt(1 - 0.98 * 0.98) * gauss() + 1;
            kb[i / B][j] += K[i][j] / B;
            vb[i / B][j] += V[i][j] / B;
        }
    for (int t = 0; t < 50; t++) {
        double q[D], o[D], oh[D], phat[M];
        for (int j = 0; j < D; j++) q[j] = 2 * gauss();
        for (int i = 0; i < N; i++) { l[i] = dot(q, K[i]); rows[i] = V[i]; }
        attend(N, l, rows, o);                                  /* exact */
        for (int w = 0; w < 2; w++) {                           /* w = 1: with ln|C| */
            for (int m = 0; m < M; m++) { lr[m] = dot(q, kb[m]) + w * log(B); rows[m] = vb[m]; }
            attend(M, lr, rows, oh);
            err[w] += relerr(o, oh) / 50;
        }
        for (int m = 0; m < M; m++) phat[m] = dot(q, kb[m]);    /* equal sizes: rank by logit */
        for (int w = 0; w < 2; w++) {                           /* mixed */
            int n = 0;
            for (int m = 0; m < M; m++) {
                int rank = 0;
                for (int m2 = 0; m2 < M; m2++) rank += phat[m2] > phat[m];
                if (rank < EXPAND)
                    for (int i = m * B; i < (m + 1) * B; i++) { lr[n] = l[i]; rows[n++] = V[i]; }
                else { lr[n] = phat[m] + w * log(B); rows[n++] = vb[m]; }
            }
            attend(n, lr, rows, oh);
            err[2 + w] += relerr(o, oh) / 50;
        }
    }
    printf("all clusters as representatives: error %.2f%% with ln|C|, %.2f%% without\n",
           100 * err[1], 100 * err[0]);
    printf("top %d clusters exact, rest reps:  error %.2f%% with ln|C|, %.2f%% without\n",
           EXPAND, 100 * err[3], 100 * err[2]);
    printf("entries read in the mixed case: %d of %d\n", EXPAND * B + (M - EXPAND), N);
    return 0;
}
