#include <math.h>
#include <stdio.h>

int main(void)
{
    double s[6] = { 2, 1, 5, 3, 9, 0 };          /* logits, seen one at a time */
    double v[6] = { 10, 20, 30, 40, 50, 60 };    /* one scalar value each */
    double m = -INFINITY, l = 0, a = 0;          /* running max, sum, weighted sum */
    for (int i = 0; i < 6; i++) {
        double mn = fmax(m, s[i]);
        double r = exp(m - mn);                  /* rescale old terms: e^(m_old - m_new) */
        l = l * r + exp(s[i] - mn);
        a = a * r + exp(s[i] - mn) * v[i];
        m = mn;
        printf("after s = %g:  m = %g  l = %.6f  o = a/l = %.6f\n", s[i], m, l, a / l);
    }
    double M = 9, L = 0, A = 0;                  /* two-pass reference */
    for (int i = 0; i < 6; i++) { L += exp(s[i] - M); A += exp(s[i] - M) * v[i]; }
    printf("two-pass:      m = %g  l = %.6f  o = %.6f\n", M, L, A / L);
    return 0;
}
