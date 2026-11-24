#include <math.h>
#include <stdio.h>

#define N 8      /* tokens */
#define D 2      /* key dimension d */
#define B 4      /* cluster size: C = {0..3} and {4..7} */

int main(void)
{
    double q[D] = { 1.5, -0.5 };
    double k[N][D] = { { 1, 0 }, { 0.5, 1 }, { 1.5, 0.5 }, { -1, 0 },
                       { 2, -1 }, { 1.8, -0.6 }, { 0, 2 }, { 2.4, -0.2 } };
    double v[N][2] = { { 1, 0 }, { 0, 1 }, { 1, 1 }, { -1, 0 },
                       { 0, -1 }, { 2, 0 }, { 1, -1 }, { 0.5, 0.5 } };
    double s[N], Z = 0, o[2] = { 0, 0 }, mix[2] = { 0, 0 };
    for (int i = 0; i < N; i++) {
        s[i] = (q[0] * k[i][0] + q[1] * k[i][1]) / sqrt(D);   /* s_i = q.k_i / sqrt d */
        Z += exp(s[i]);
    }
    for (int i = 0; i < N; i++) {                               /* o = sum alpha_i v_i */
        double alpha = exp(s[i]) / Z;
        o[0] += alpha * v[i][0];
        o[1] += alpha * v[i][1];
    }
    for (int c = 0; c < N / B; c++) {
        double zC = 0, vC[2] = { 0, 0 };
        for (int i = c * B; i < c * B + B; i++) zC += exp(s[i]);
        for (int i = c * B; i < c * B + B; i++) {               /* w_{i|C} = e^{s_i} / z_C */
            vC[0] += exp(s[i]) / zC * v[i][0];
            vC[1] += exp(s[i]) / zC * v[i][1];
        }
        double pC = zC / Z;
        printf("cluster %d: p_C = %.4f, v_C = (%.4f, %.4f)\n", c, pC, vC[0], vC[1]);
        mix[0] += pC * vC[0];
        mix[1] += pC * vC[1];
    }
    printf("sum alpha_i v_i = (%.15f, %.15f)\n", o[0], o[1]);
    printf("sum p_C v_C     = (%.15f, %.15f)\n", mix[0], mix[1]);
    return 0;
}
