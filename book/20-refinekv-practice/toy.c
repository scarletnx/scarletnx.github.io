/* toy.c: a toy RefineKV. Blocks of 32 keys, box bound, risk scores, expand above tau,
   one attention over the mixed set merged by online softmax. */
#include <math.h>
#include <stdio.h>
#include <stdlib.h>

#define N 8192                      /* cached tokens */
#define D 64                        /* head dimension (keys and values) */
#define B 32                        /* block size |C| */
#define NB (N / B)
#define H 4                         /* query heads sharing one KV head (GQA) */
#define STEPS 64                    /* decode queries */

static double k[N][D], v[N][D], kb[NB][D], vb[NB][D], lo[NB][D], hi[NB][D], VC[NB], Vmax;

static double U(void) { return (rand() + 0.5) / (RAND_MAX + 1.0); }
static double G(void) { return sqrt(-2 * log(U())) * cos(6.283185307179586 * U()); }
static double dot(const double *a, const double *b) { double s = 0; for (int j = 0; j < D; j++) s += a[j] * b[j]; return s; }

typedef struct { double m, l, acc[D]; } Run;        /* online softmax state */
static void push(Run *r, double s, const double *val)
{
    if (s > r->m) { double c = exp(r->m - s); r->l *= c; for (int j = 0; j < D; j++) r->acc[j] *= c; r->m = s; }
    double e = exp(s - r->m);
    r->l += e;
    for (int j = 0; j < D; j++) r->acc[j] += e * val[j];
}
static void merge(Run *a, const Run *b)              /* fold partial b into a */
{
    double m = fmax(a->m, b->m), ca = exp(a->m - m), cb = exp(b->m - m);
    a->l = a->l * ca + b->l * cb;
    for (int j = 0; j < D; j++) a->acc[j] = a->acc[j] * ca + b->acc[j] * cb;
    a->m = m;
}
static Run empty(void) { Run r = { -INFINITY, 0, {0} }; return r; }

/* output with blocks where ex[c] != 0 exact, the rest by (kbar + log B, vbar); relative error */
static double attend(const double *q, const char *ex)
{
    Run full = empty(), exact = empty(), rep = empty();
    double sq = sqrt(D), e2 = 0, o2 = 0;
    for (int c = 0; c < NB; c++) {
        for (int i = c * B; i < (c + 1) * B; i++) {
            double s = dot(q, k[i]) / sq;
            push(&full, s, v[i]);
            if (ex[c]) push(&exact, s, v[i]);
        }
        if (!ex[c]) push(&rep, dot(q, kb[c]) / sq + log(B), vb[c]);
    }
    merge(&exact, &rep);
    for (int j = 0; j < D; j++) {
        double o = full.acc[j] / full.l, oh = exact.acc[j] / exact.l;
        e2 += (o - oh) * (o - oh); o2 += o * o;
    }
    return sqrt(e2 / o2);
}

/* risk scores R_C of Eq. 4 with the box bound of A.7.1 */
static void risk(const double *q, double *R, double *ph)
{
    double sq = sqrt(D), s[NB], dl[NB], mx = -1e300, z = 0, den = 0;
    for (int c = 0; c < NB; c++) {
        double up = 0, dn = 0;
        s[c] = dot(q, kb[c]) / sq;
        for (int j = 0; j < D; j++) { up += fmax(q[j] * lo[c][j], q[j] * hi[c][j]); dn += fmin(q[j] * lo[c][j], q[j] * hi[c][j]); }
        dl[c] = fmax(up / sq - s[c], s[c] - dn / sq);
        if (s[c] > mx) mx = s[c];
    }
    for (int c = 0; c < NB; c++) z += exp(s[c] - mx);
    for (int c = 0; c < NB; c++) { ph[c] = exp(s[c] - mx) / z; den += ph[c] * cosh(dl[c]); }
    for (int c = 0; c < NB; c++) R[c] = ph[c] * (Vmax * (cosh(dl[c]) - 1) / den + VC[c] * tanh(dl[c] / 2));
}

int main(void)
{
    static double R[STEPS][H][NB], P[STEPS][H][NB], q[STEPS][H][D];
    double taus[] = { 1e-4, 1e-3, 1e-2, 0.03, 0.1, 0.3, 1, INFINITY }, full = (double)N * 2 * D;
    srand(20);
    for (int i = 0; i < N;) {                         /* segments: keys near a topic, values near another */
        double t[D], w[D];
        int len = 40 + rand() % 400;
        for (int j = 0; j < D; j++) { t[j] = G(); w[j] = G(); }
        for (; len-- > 0 && i < N; i++)
            for (int j = 0; j < D; j++) { k[i][j] = t[j] + 0.4 * G(); v[i][j] = w[j] + 0.5 * G(); }
    }
    for (int c = 0; c < NB; c++) {                    /* prefill: representatives and box metadata */
        VC[c] = 0;
        for (int j = 0; j < D; j++) { kb[c][j] = vb[c][j] = 0; lo[c][j] = 1e300; hi[c][j] = -1e300; }
        for (int i = c * B; i < (c + 1) * B; i++) {
            for (int j = 0; j < D; j++) {
                kb[c][j] += k[i][j] / B; vb[c][j] += v[i][j] / B;
                lo[c][j] = fmin(lo[c][j], k[i][j]); hi[c][j] = fmax(hi[c][j], k[i][j]);
            }
            VC[c] = fmax(VC[c], sqrt(dot(v[i], v[i])));
        }
        Vmax = fmax(Vmax, VC[c]);
    }
    for (int t = 0; t < STEPS; t++) {                 /* queries: near some earlier key, varied sharpness */
        int at = rand() % N;
        for (int h = 0; h < H; h++) {
            double a = 0.2 + U();
            for (int j = 0; j < D; j++) q[t][h][j] = a * (k[at][j] + 0.8 * G());
            risk(q[t][h], R[t][h], P[t][h]);
        }
    }
    printf("    tau  policy  expanded  bytes read  mean err   max err  | p-hat top-k, same budget\n");
    for (int x = 0; x < 8; x++)
        for (int pol = 0; pol < 2; pol++) {           /* 0: GQA-any, 1: GQA-mean */
            double nexp = 0, err = 0, emax = 0, perr = 0;
            if (pol == 1 && taus[x] != 1e-2 && taus[x] != 0.1) continue;
            for (int t = 0; t < STEPS; t++) {
                char ex[NB], top[NB];
                int cnt = 0;
                double key[NB];
                for (int c = 0; c < NB; c++) {
                    double mx = 0, mean = 0, pm = 0;
                    for (int h = 0; h < H; h++) { mx = fmax(mx, R[t][h][c]); mean += R[t][h][c] / H; pm = fmax(pm, P[t][h][c]); }
                    ex[c] = (pol ? mean : mx) > taus[x];
                    cnt += ex[c]; key[c] = pm; top[c] = 0;
                }
                for (int e = 0; e < cnt; e++) {         /* the cnt blocks of largest p-hat */
                    int best = -1;
                    for (int c = 0; c < NB; c++) if (!top[c] && (best < 0 || key[c] > key[best])) best = c;
                    top[best] = 1;
                }
                nexp += (double)cnt / NB;
                for (int h = 0; h < H; h++) {
                    double e = attend(q[t][h], ex);
                    err += e / (STEPS * H); emax = fmax(emax, e); perr += attend(q[t][h], top) / (STEPS * H);
                }
            }
            nexp /= STEPS;
            /* per block: scoring reads kbar, lo, hi, V_C; then vbar or the 32 exact (k, v) */
            double bytes = NB * (3.0 * D + 1) + NB * ((1 - nexp) * D + nexp * B * 2.0 * D);
            printf("%7.0e  %-6s  %7.1f%%  %9.1f%%  %8.2e  %8.2e  | %8.2e\n", taus[x], pol ? "mean" : "any",
                   100 * nexp, 100 * bytes / full, err, emax, perr);
        }
    return 0;
}
