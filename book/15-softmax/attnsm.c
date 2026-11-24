#include <math.h>
#include <stdio.h>

enum { N = 32768, DV = 64, B = 32 };
static float s[N], v[N][DV];

typedef struct { float m, l, a[DV]; } State;   /* running max, sum, unnormalized output */

static void push(State *st, float si, const float *vi)  /* online update with one key */
{
    float mn = fmaxf(st->m, si), r = expf(st->m - mn), p = expf(si - mn);
    st->l = st->l * r + p;
    for (int j = 0; j < DV; j++) st->a[j] = st->a[j] * r + p * vi[j];
    st->m = mn;
}

static void merge(State *x, const State *y)              /* x = merge(x, y) */
{
    float mn = fmaxf(x->m, y->m), rx = expf(x->m - mn), ry = expf(y->m - mn);
    x->l = x->l * rx + y->l * ry;
    for (int j = 0; j < DV; j++) x->a[j] = x->a[j] * rx + y->a[j] * ry;
    x->m = mn;
}

static double maxerr(const State *st, const double *ref)
{
    double e = 0;
    for (int j = 0; j < DV; j++) e = fmax(e, fabs(st->a[j] / st->l - ref[j]));
    return e;
}

int main(void)
{
    for (int i = 0; i < N; i++) {
        s[i] = (float)(40 * sin(0.37 * i) * sin(0.0011 * i * i));      /* logits in [-40, 40] */
        for (int j = 0; j < DV; j++) v[i][j] = (float)cos(0.11 * i + j);
    }
    double m = s[0], l = 0, ref[DV] = { 0 };                 /* reference: two passes, double */
    for (int i = 1; i < N; i++) m = fmax(m, s[i]);
    for (int i = 0; i < N; i++) {
        double p = exp(s[i] - m);
        l += p;
        for (int j = 0; j < DV; j++) ref[j] += p * v[i][j];
    }
    for (int j = 0; j < DV; j++) ref[j] /= l;

    State two = { (float)m, 0, { 0 } };                      /* two passes, float */
    for (int i = 0; i < N; i++) {
        float p = expf(s[i] - two.m);
        two.l += p;
        for (int j = 0; j < DV; j++) two.a[j] += p * v[i][j];
    }
    State on = { -INFINITY, 0, { 0 } }, all = { -INFINITY, 0, { 0 } };
    for (int i = 0; i < N; i++) push(&on, s[i], v[i]);       /* one pass, float */
    for (int c = 0; c < N / B; c++) {                        /* chunks of B, merged */
        State ch = { -INFINITY, 0, { 0 } };
        for (int i = c * B; i < (c + 1) * B; i++) push(&ch, s[i], v[i]);
        merge(&all, &ch);
    }
    printf("N = %d, max logit %.3f, sum l = %.6f\n", N, m, l);
    printf("max |o_j - ref_j|:  two-pass %.1e  one-pass %.1e  merged chunks %.1e\n",
           maxerr(&two, ref), maxerr(&on, ref), maxerr(&all, ref));
    return 0;
}
