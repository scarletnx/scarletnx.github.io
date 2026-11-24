/* mono.c: R_C of one cluster falls when another cluster's delta grows; the sum does not. */
#include <math.h>
#include <stdio.h>

int main(void)
{
    double p[2] = { 0.5, 0.5 }, V = 1, d1 = 1;     /* V_C = V_max = 1 */
    for (double d2 = 0; d2 <= 3; d2 += 1) {
        double S = p[0] * cosh(d1) + p[1] * cosh(d2);
        double R1 = p[0] * (V * (cosh(d1) - 1) / S + V * tanh(d1 / 2));
        double R2 = p[1] * (V * (cosh(d2) - 1) / S + V * tanh(d2 / 2));
        printf("delta_2 = %.0f: R_1 = %.4f  R_2 = %.4f  2(R_1 + R_2) = %.4f\n", d2, R1, R2, 2 * (R1 + R2));
    }
    /* exercise 1: cluster A = one token at logit 0, cluster B = two tokens at logits +1, -1 */
    double zA = 1, zB = exp(1) + exp(-1), zhA = 1, zhB = 2;
    printf("p_A = %.4f  phat_A = %.4f  m_B = %.4f  cosh 1 = %.4f\n", zA / (zA + zB), zhA / (zhA + zhB), zB / zhB, cosh(1));
    return 0;
}
