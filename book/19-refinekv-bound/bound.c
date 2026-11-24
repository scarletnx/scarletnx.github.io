/* bound.c: every step of RefineKV's Appendix A, checked on random clusters. */
#include <math.h>
#include <stdio.h>
#include <stdlib.h>

#define D 16                        /* key dimension d */
#define DV 8                        /* value dimension d_v */
#define NC 64                       /* most tokens per cluster */
#define MC 24                       /* most clusters */
#define TRIALS 20000
#define NCHK 11

static double U(void) { return (rand() + 0.5) / (RAND_MAX + 1.0); }
static double G(void) { return sqrt(-2 * log(U())) * cos(6.283185307179586 * U()); }
static double dot(const double *a, const double *b, int n)
{ double s = 0; for (int j = 0; j < n; j++) s += a[j] * b[j]; return s; }
static int cmp(const void *a, const void *b)
{ double x = *(const double *)a, y = *(const double *)b; return (x > y) - (x < y); }

static const char *name[NCHK] = {
    "m_C >= 1                      (Eq. 38, 50)", "m_C <= cosh(delta_C)          (Lemma A.2)",
    "sum |w - 1/n| <= 2 tanh(d/2)  (Eq. 29)", "|v_C - vbar_C| <= 2V_C tanh   (Eq. 30)",
    "|o - otilde| <= Eq. 22", "|otilde - ohat| <= Eq. 32",
    "|o - ohat| <= 2 sum R_C exact (Eq. 35)", "delta_C <= delta_box          (Eq. 83)",
    "delta_C <= delta_ell          (Eq. 91)", "|o - ohat| <= 2 sum R_C box   (Eq. 37)",
    "|o - ohat| <= 2 sum R_C ell   (Eq. 37)" };
static double worst[NCHK];
static long bad[NCHK];
static void check(int c, double lhs, double rhs)
{
    if (lhs > rhs * (1 + 1e-9) + 1e-12) bad[c]++;
    if (rhs > 0 && lhs / rhs > worst[c]) worst[c] = lhs / rhs;
}

static int m, n[MC];
static double k[MC][NC][D], v[MC][NC][DV], q[D], ph[MC], V[MC], Vmax;

/* 2 * sum_C R_C (Eq. 4) for logit spreads dl[] */
static double bound(const double *dl)
{
    double den = 0, r = 0;
    for (int c = 0; c < m; c++) den += ph[c] * cosh(dl[c]);
    for (int c = 0; c < m; c++)
        r += ph[c] * (Vmax * (cosh(dl[c]) - 1) / den + V[c] * tanh(dl[c] / 2));
    return 2 * r;
}

int main(void)
{
    static double rex[TRIALS], rbox[TRIALS], qb[TRIALS * MC], qe[TRIALS * MC];
    long nq = 0;
    double res = 0, sq = sqrt(D);
    long vac_ex = 0, vac_box = 0;
    srand(19);
    for (int t = 0; t < TRIALS; t++) {
        double qs = 0.5 + 2.5 * U(), s[MC][NC], sC[MC], smax = -1e300;
        m = 2 + rand() % (MC - 1);
        for (int j = 0; j < D; j++) q[j] = qs * G();
        for (int c = 0; c < m; c++) {               /* cluster: centre + spread */
            double ck[D], cv[DV], sp = U() * U();
            n[c] = 1 + rand() % NC;
            for (int j = 0; j < D; j++) ck[j] = 1.5 * G();
            for (int j = 0; j < DV; j++) cv[j] = G();
            for (int i = 0; i < n[c]; i++) {
                for (int j = 0; j < D; j++) k[c][i][j] = ck[j] + sp * G();
                for (int j = 0; j < DV; j++) v[c][i][j] = cv[j] + 0.5 * G();
            }
        }
        double kb[MC][D], vb[MC][DV], vC[MC][DV], z[MC], zh[MC], mC[MC];
        double dl[MC], dbox[MC], dell[MC], Z = 0, Zh = 0, M = 0;
        Vmax = 0;
        for (int c = 0; c < m; c++) {               /* means, logits, Eq. 5-7 */
            for (int j = 0; j < D; j++) {
                kb[c][j] = 0;
                for (int i = 0; i < n[c]; i++) kb[c][j] += k[c][i][j] / n[c];
            }
            sC[c] = dot(q, kb[c], D) / sq;
            if (sC[c] + log(n[c]) > smax) smax = sC[c] + log(n[c]);
            V[c] = 0;
            for (int i = 0; i < n[c]; i++) {
                s[c][i] = dot(q, k[c][i], D) / sq;
                if (s[c][i] > smax) smax = s[c][i];
                double nv = sqrt(dot(v[c][i], v[c][i], DV));
                if (nv > V[c]) V[c] = nv;
            }
            if (V[c] > Vmax) Vmax = V[c];
        }
        for (int c = 0; c < m; c++) {               /* masses, Eq. 7-10 */
            z[c] = 0; zh[c] = n[c] * exp(sC[c] - smax); mC[c] = 0; dl[c] = 0;
            for (int j = 0; j < DV; j++) vC[c][j] = vb[c][j] = 0;
            for (int i = 0; i < n[c]; i++) {
                double e = exp(s[c][i] - smax);
                z[c] += e;
                mC[c] += exp(s[c][i] - sC[c]) / n[c];
                if (fabs(s[c][i] - sC[c]) > dl[c]) dl[c] = fabs(s[c][i] - sC[c]);
                for (int j = 0; j < DV; j++) { vC[c][j] += e * v[c][i][j]; vb[c][j] += v[c][i][j] / n[c]; }
            }
            for (int j = 0; j < DV; j++) vC[c][j] /= z[c];
            Z += z[c]; Zh += zh[c];
        }
        double o[DV] = {0}, oh[DV] = {0}, ot[DV] = {0}, p[MC];
        for (int c = 0; c < m; c++) {
            p[c] = z[c] / Z; ph[c] = zh[c] / Zh; M += ph[c] * mC[c];
            for (int j = 0; j < DV; j++) {
                o[j] += p[c] * vC[c][j]; oh[j] += ph[c] * vb[c][j]; ot[j] += ph[c] * vC[c][j];
            }
        }
        double e1 = 0, e2 = 0, e = 0, r17 = 0, r3 = 0, rhs22, rhs32 = 0, den = 0;
        for (int j = 0; j < DV; j++) {
            double a = 0, b = 0;                    /* right sides of Eq. 17 and Eq. 3 */
            for (int c = 0; c < m; c++) {
                a += ph[c] * (mC[c] - 1) / M * (vC[c][j] - ot[j]);
                b += (p[c] - ph[c]) * vC[c][j] + ph[c] * (vC[c][j] - vb[c][j]);
            }
            r17 += pow(o[j] - ot[j] - a, 2); r3 += pow(o[j] - oh[j] - b, 2);
            e1 += pow(o[j] - ot[j], 2); e2 += pow(ot[j] - oh[j], 2); e += pow(o[j] - oh[j], 2);
        }
        if (sqrt(r17 + r3) > res) res = sqrt(r17 + r3);
        e1 = sqrt(e1); e2 = sqrt(e2); e = sqrt(e);
        for (int c = 0; c < m; c++) {
            double tv = 0, dv2 = 0, su = 0, sl = 0, w[D], rho = 0, qw = 0;
            check(0, 1, mC[c]);
            check(1, mC[c], cosh(dl[c]));
            for (int i = 0; i < n[c]; i++) tv += fabs(exp(s[c][i] - smax) / z[c] - 1.0 / n[c]);
            check(2, tv, 2 * tanh(dl[c] / 2));
            for (int j = 0; j < DV; j++) dv2 += pow(vC[c][j] - vb[c][j], 2);
            check(3, sqrt(dv2), 2 * V[c] * tanh(dl[c] / 2));
            for (int j = 0; j < D; j++) {           /* box (A.7.1) and ellipsoid (A.7.2) */
                double lo = 1e300, hi = -1e300;
                w[j] = 0;
                for (int i = 0; i < n[c]; i++) {
                    if (k[c][i][j] < lo) lo = k[c][i][j];
                    if (k[c][i][j] > hi) hi = k[c][i][j];
                    if (fabs(k[c][i][j] - kb[c][j]) > w[j]) w[j] = fabs(k[c][i][j] - kb[c][j]);
                }
                su += fmax(q[j] * lo, q[j] * hi) / sq; sl += fmin(q[j] * lo, q[j] * hi) / sq;
                qw += q[j] * q[j] * w[j] * w[j];
            }
            for (int i = 0; i < n[c]; i++) {
                double r2 = 0;
                for (int j = 0; j < D; j++)
                    if (w[j] > 0) r2 += pow((k[c][i][j] - kb[c][j]) / w[j], 2);
                if (sqrt(r2) > rho) rho = sqrt(r2);
            }
            dbox[c] = fmax(fabs(su - sC[c]), fabs(sl - sC[c]));
            dell[c] = rho * sqrt(qw) / sq;
            check(7, dl[c], dbox[c]); check(8, dl[c], dell[c]);
            if (dl[c] > 0) { qb[nq] = dbox[c] / dl[c]; qe[nq++] = dell[c] / dl[c]; }
            den += ph[c] * cosh(dl[c]); rhs32 += 2 * ph[c] * V[c] * tanh(dl[c] / 2);
        }
        rhs22 = 2 * Vmax * (1 - 1 / den);
        check(4, e1, rhs22); check(5, e2, rhs32);
        check(6, e, bound(dl)); check(9, e, bound(dbox)); check(10, e, bound(dell));
        rex[t] = bound(dl) / e; rbox[t] = bound(dbox) / e;
        vac_ex += bound(dl) > 2 * Vmax; vac_box += bound(dbox) > 2 * Vmax;
    }
    printf("%d trials; identities Eq. 3 and Eq. 17: largest residual %.1e\n", TRIALS, res);
    printf("%-44s %10s %8s\n", "inequality", "violations", "max l/r");
    for (int c = 0; c < NCHK; c++) printf("%-44s %10ld %8.4f\n", name[c], bad[c], worst[c]);
    qsort(rex, TRIALS, sizeof *rex, cmp); qsort(rbox, TRIALS, sizeof *rbox, cmp);
    printf("bound / |o - ohat|   min    10%%    50%%    90%%\n");
    printf("exact delta     %7.2f %6.2f %6.2f %6.1f\n", rex[0], rex[TRIALS / 10], rex[TRIALS / 2], rex[9 * TRIALS / 10]);
    printf("box delta       %7.2f %6.2f %6.1f %6.0f\n", rbox[0], rbox[TRIALS / 10], rbox[TRIALS / 2], rbox[9 * TRIALS / 10]);
    printf("bound above the trivial 2 Vmax: exact %.1f%%, box %.1f%%\n",
           100.0 * vac_ex / TRIALS, 100.0 * vac_box / TRIALS);
    qsort(qb, nq, sizeof *qb, cmp); qsort(qe, nq, sizeof *qe, cmp);
    printf("delta_box / delta: median %.2f, 90%% %.2f;  delta_ell / delta: median %.2f, 90%% %.2f\n",
           qb[nq / 2], qb[9 * nq / 10], qe[nq / 2], qe[9 * nq / 10]);
    return 0;
}
