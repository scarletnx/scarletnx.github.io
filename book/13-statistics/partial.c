#include <math.h>
#include <stdio.h>

#define M 10                                  /* clusters in one (step, layer, head) */

static double pearson(const double *x, const double *y)
{
    double mx = 0, my = 0, sxy = 0, sxx = 0, syy = 0;
    for (int i = 0; i < M; i++) { mx += x[i] / M; my += y[i] / M; }
    for (int i = 0; i < M; i++) {
        sxy += (x[i] - mx) * (y[i] - my);
        sxx += (x[i] - mx) * (x[i] - mx);
        syy += (y[i] - my) * (y[i] - my);
    }
    return sxy / sqrt(sxx * syy);
}

static void ranks(const double *x, double *r)  /* ties share their average rank */
{
    for (int i = 0; i < M; i++) {
        int below = 0, equal = 0;
        for (int j = 0; j < M; j++) { below += x[j] < x[i]; equal += x[j] == x[i]; }
        r[i] = below + (equal + 1) / 2.0;
    }
}

static void residual(const double *y, const double *x, double *e)   /* y - (a + b x) */
{
    double mx = 0, my = 0, sxy = 0, sxx = 0;
    for (int i = 0; i < M; i++) { mx += x[i] / M; my += y[i] / M; }
    for (int i = 0; i < M; i++) { sxy += (x[i] - mx) * (y[i] - my); sxx += (x[i] - mx) * (x[i] - mx); }
    for (int i = 0; i < M; i++) e[i] = y[i] - my - sxy / sxx * (x[i] - mx);
}

int main(void)
{
    double p[M] = { .0071, .416, .217, .00615, .0137, .0335, .0225, .176, .0234, .0847 };
    double s[M] = { .00255, .268, .294, .000663, .0113, .0145, .382, .277, .00566, .0262 };
    double y[M] = { .000775, .0678, .0634, .000452, .00385, .00793, .0379, .152, .0045, .0147 };
    double rp[M], rs[M], ry[M], es[M], ey[M];
    ranks(p, rp); ranks(s, rs); ranks(y, ry);
    double rsy = pearson(rs, ry), rsp = pearson(rs, rp), ryp = pearson(ry, rp);
    printf("Spearman: score-error %.4f, mass-error %.4f, score-mass %.4f\n", rsy, ryp, rsp);
    residual(rs, rp, es);                     /* the part of each rank mass cannot predict */
    residual(ry, rp, ey);
    printf("partial, from residuals: %.4f\n", pearson(es, ey));
    printf("partial, from formula:   %.4f\n", (rsy - rsp * ryp) / sqrt((1 - rsp * rsp) * (1 - ryp * ryp)));
    return 0;
}
