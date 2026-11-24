#include <math.h>
#include <stdio.h>

/* logit deviation q.(k - kbar) of a key close to its cluster mean, two ways, in float */
int main(void)
{
    enum { D = 128 };
    float q[D], k[D], kb[D];
    for (int j = 0; j < D; j++) {
        q[j] = (float)sin(j + 1.0);
        kb[j] = 10.0f + (float)cos(3.0 * j);           /* large common part */
        k[j] = kb[j] + 1e-3f * (float)sin(7.0 * j);     /* small offset */
    }
    float qk = 0, qkb = 0, qd = 0;
    double ref = 0;
    for (int j = 0; j < D; j++) {
        qk += q[j] * k[j];
        qkb += q[j] * kb[j];
        qd += q[j] * (k[j] - kb[j]);
        ref += (double)q[j] * ((double)k[j] - (double)kb[j]);
    }
    printf("q.k - q.kbar = %.6e (rel err %.1e)\n", qk - qkb, fabs((qk - qkb - ref) / ref));
    printf("q.(k - kbar) = %.6e (rel err %.1e)\n", qd, fabs((qd - ref) / ref));
    return 0;
}
