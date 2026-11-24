#include <math.h>
#include <stdio.h>
#include <stdlib.h>

#define D 128                     /* d_k */
#define C 32                      /* |C|: the paper's block size */

static double gauss(void)
{
    double u = (rand() + 1.0) / (RAND_MAX + 2.0), v = (rand() + 1.0) / (RAND_MAX + 2.0);
    return sqrt(-2 * log(u)) * cos(6.283185307179586 * v);
}

/* keys: 0 dense, 1 one spike per key, 2 along one line.  query: 0 dense, 1 one spike.
   out: delta_C, delta_box, delta_ell, rho_C, |x|_1/|x|_2 with x_j = q_j w_Cj */
static void trial(int keys, int query, double out[5])
{
    double k[C][D], kb[D] = { 0 }, q[D], u[D], lo[D], hi[D], w[D];
    double rho = 0, dev = 0, up = 0, dn = 0, qw = 0, l1 = 0;
    for (int j = 0; j < D; j++) { u[j] = gauss(); q[j] = query ? 0.1 * gauss() : gauss(); }
    if (query) q[rand() % D] += 5;
    for (int i = 0; i < C; i++) {
        double t = gauss();
        for (int j = 0; j < D; j++)
            k[i][j] = keys == 0 ? gauss() : keys == 2 ? t * u[j] + 0.1 * gauss() : 0.1 * gauss();
        if (keys == 1) k[i][rand() % D] += 3 * gauss();
        for (int j = 0; j < D; j++) kb[j] += k[i][j] / C;           /* mean key */
    }
    for (int j = 0; j < D; j++) { lo[j] = INFINITY; hi[j] = -INFINITY; }
    for (int i = 0; i < C; i++)
        for (int j = 0; j < D; j++) {                               /* r_ij = k_ij - kbar_j */
            k[i][j] -= kb[j];
            lo[j] = fmin(lo[j], k[i][j]); hi[j] = fmax(hi[j], k[i][j]);
        }
    for (int j = 0; j < D; j++) w[j] = fmax(-lo[j], hi[j]);         /* w_Cj */
    for (int i = 0; i < C; i++) {
        double n = 0, s = 0;
        for (int j = 0; j < D; j++) { n += k[i][j] * k[i][j] / (w[j] * w[j]); s += q[j] * k[i][j]; }
        rho = fmax(rho, sqrt(n));                                   /* rho_C */
        dev = fmax(dev, fabs(s));                                   /* max |q.r_i| */
    }
    for (int j = 0; j < D; j++) {
        up += fmax(q[j] * lo[j], q[j] * hi[j]);                     /* max over the box */
        dn += fmin(q[j] * lo[j], q[j] * hi[j]);                     /* min over the box */
        qw += q[j] * q[j] * w[j] * w[j];
        l1 += fabs(q[j]) * w[j];
    }
    out[0] = dev / sqrt(D);
    out[1] = fmax(fabs(up), fabs(dn)) / sqrt(D);
    out[2] = rho * sqrt(qw) / sqrt(D);
    out[3] = rho;
    out[4] = l1 / sqrt(qw);
}

int main(void)
{
    const char *name[4] = { "dense keys, dense q", "dense keys, spiky q",
                            "spiky keys, dense q", "keys on a line, dense q" };
    int kind[4][2] = { { 0, 0 }, { 0, 1 }, { 1, 0 }, { 2, 0 } };
    srand(10);
    printf("%-24s %7s %7s %7s %6s %7s %11s %5s\n", "", "delta_C", "box", "ell", "rho_C", "l1/l2",
           "box tighter", "fails");
    for (int s = 0; s < 4; s++) {
        double m[5] = { 0 }, o[5];
        int box = 0, fail = 0, T = 2000;
        for (int t = 0; t < T; t++) {
            trial(kind[s][0], kind[s][1], o);
            for (int i = 0; i < 5; i++) m[i] += o[i] / T;
            box += o[1] < o[2];
            fail += o[1] < o[0] * (1 - 1e-12) || o[2] < o[0] * (1 - 1e-12);
        }
        printf("%-24s %7.3f %7.3f %7.3f %6.2f %7.2f %10.1f%% %5d\n", name[s], m[0], m[1], m[2],
               m[3], m[4], 100.0 * box / T, fail);
    }
    return 0;
}
