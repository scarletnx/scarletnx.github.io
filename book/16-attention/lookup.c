#include <math.h>
#include <stdio.h>

int main(void)
{
    /* four keys on the unit circle, each with a value; the query is near key 1 */
    double ang[4] = { 0.0, 1.2, 2.4, 4.0 }, v[4] = { 10, 20, 30, 40 };
    double q[2] = { cos(1.0), sin(1.0) };
    double scales[4] = { 1, 4, 16, 64 };
    for (int t = 0; t < 4; t++) {
        double s[4], w[4], m = -INFINITY, l = 0, o = 0;
        for (int i = 0; i < 4; i++) {
            s[i] = scales[t] * (q[0] * cos(ang[i]) + q[1] * sin(ang[i]));   /* scaled q.k_i */
            m = fmax(m, s[i]);
        }
        for (int i = 0; i < 4; i++) l += w[i] = exp(s[i] - m);
        for (int i = 0; i < 4; i++) { w[i] /= l; o += w[i] * v[i]; }
        printf("scale %2.0f: weights %.3f %.3f %.3f %.3f  output %.2f\n",
               scales[t], w[0], w[1], w[2], w[3], o);
    }
    return 0;
}
