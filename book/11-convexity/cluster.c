#include <math.h>
#include <stdio.h>
#include <stdlib.h>

#define D 64     /* key dimension d */
#define NC 32    /* cluster size n_C */

static double unif(void) { return 2.0 * rand() / RAND_MAX - 1; }   /* in [-1, 1] */

int main(void)
{
    double q[D], k[NC][D], kbar[D] = { 0 }, sC = 0, smean = 0, dC = 0, mC = 0;
    srand(4);
    for (int j = 0; j < D; j++) q[j] = unif();
    for (int i = 0; i < NC; i++)
        for (int j = 0; j < D; j++) { k[i][j] = unif(); kbar[j] += k[i][j] / NC; }
    for (int j = 0; j < D; j++) sC += q[j] * kbar[j] / sqrt(D);      /* representative logit */
    for (int i = 0; i < NC; i++) {
        double si = 0;
        for (int j = 0; j < D; j++) si += q[j] * k[i][j] / sqrt(D);  /* token logit s_i */
        smean += si / NC;
        if (fabs(si - sC) > dC) dC = fabs(si - sC);                    /* delta_C */
        mC += exp(si - sC) / NC;                                       /* m_C = z_C / zhat_C */
    }
    printf("s_C = %.6f, mean of s_i = %.6f\n", sC, smean);
    printf("delta_C = %.4f: 1 <= m_C = %.4f <= cosh(delta_C) = %.4f\n", dC, mC, cosh(dC));
    return 0;
}
