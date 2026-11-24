#include <math.h>
#include <stdio.h>

int main(void)
{
    enum { T = 5 };
    double s[T][T];
    for (int i = 0; i < T; i++)                 /* some logits s_ij = q_i.k_j / sqrt(d) */
        for (int j = 0; j < T; j++)
            s[i][j] = j > i ? -INFINITY : sin(1.0 + i * 2.1 + j * 1.3);   /* causal mask */
    for (int i = 0; i < T; i++) {
        double m = -INFINITY, l = 0;
        for (int j = 0; j < T; j++) m = fmax(m, s[i][j]);
        for (int j = 0; j < T; j++) l += exp(s[i][j] - m);
        printf("query %d:", i);
        for (int j = 0; j < T; j++) printf(" %.3f", exp(s[i][j] - m) / l);
        printf("\n");
    }
    return 0;
}
