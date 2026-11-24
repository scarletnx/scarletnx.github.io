/* How spread makes error. 64 clusters of 32 tokens, d = 64. Keys are
   k_i = center_C + sigma u_i, values v_i = vcenter_C + tau w_i (u, w normal).
   For each sigma, tau: mean over 20 queries of the mean delta_C and of the
   relative error |o - ohat| / |o| of attention over representatives. */
#include <math.h>
#include <stdio.h>
#include <stdlib.h>

#define M 64
#define B 32
#define N (M * B)
#define D 64

static double ck[M][D], cv[M][D], U[N][D], W[N][D];

static double gauss(void)
{
    double u = (rand() + 1.0) / (RAND_MAX + 2.0), v = (rand() + 1.0) / (RAND_MAX + 2.0);
    return sqrt(-2 * log(u)) * cos(6.283185307179586 * v);
}

int main(void)
{
    double sig[] = { 0, 0.05, 0.1, 0.2, 0.4, 0.8 }, tau[] = { 0, 1, 4 };
    srand(7);
    for (int m = 0; m < M; m++)
        for (int j = 0; j < D; j++) { ck[m][j] = gauss(); cv[m][j] = 1 + gauss(); }
    for (int i = 0; i < N; i++)
        for (int j = 0; j < D; j++) { U[i][j] = gauss(); W[i][j] = gauss(); }
    for (int a = 0; a < 6; a++) {
        printf("sigma %.2f:", sig[a]);
        for (int b = 0; b < 3; b++) {
            double err = 0, delta = 0;
            srand(8);                                   /* same queries each time */
            for (int t = 0; t < 20; t++) {
                double q[D], o[D] = { 0 }, oh[D] = { 0 }, z = 0, zh = 0, e = 0, n = 0;
                for (int j = 0; j < D; j++) q[j] = gauss();
                for (int m = 0; m < M; m++) {
                    double kb[D] = { 0 }, vb[D] = { 0 }, s[B], sb = 0, dC = 0;
                    for (int i = 0; i < B; i++)
                        for (int j = 0; j < D; j++) {
                            kb[j] += (ck[m][j] + sig[a] * U[m * B + i][j]) / B;
                            vb[j] += (cv[m][j] + tau[b] * W[m * B + i][j]) / B;
                        }
                    for (int j = 0; j < D; j++) sb += q[j] * kb[j] / sqrt(D);
                    for (int i = 0; i < B; i++) {
                        s[i] = 0;
                        for (int j = 0; j < D; j++) s[i] += q[j] * (ck[m][j] + sig[a] * U[m * B + i][j]);
                        s[i] /= sqrt(D);
                        if (fabs(s[i] - sb) > dC) dC = fabs(s[i] - sb);
                        z += exp(s[i]);
                        for (int j = 0; j < D; j++) o[j] += exp(s[i]) * (cv[m][j] + tau[b] * W[m * B + i][j]);
                    }
                    zh += B * exp(sb);                          /* |C| e^{q.kbar/sqrt d} */
                    for (int j = 0; j < D; j++) oh[j] += B * exp(sb) * vb[j];
                    delta += dC / (20.0 * M);
                }
                for (int j = 0; j < D; j++) { e += pow(o[j] / z - oh[j] / zh, 2); n += pow(o[j] / z, 2); }
                err += sqrt(e / n) / 20;
            }
            if (b == 0) printf(" mean delta %.3f |", delta);
            printf("  tau %g: %.2e", tau[b], err);
        }
        printf("\n");
    }
    return 0;
}
