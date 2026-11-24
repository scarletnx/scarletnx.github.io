#include <math.h>
#include <stdio.h>

typedef struct { double m, l, a; } State;      /* max, sum e^(s-m), sum e^(s-m) v */

static State merge(State x, State y)
{
    if (x.l == 0) return y;                    /* empty state: m = -inf */
    if (y.l == 0) return x;
    double m = fmax(x.m, y.m), ex = exp(x.m - m), ey = exp(y.m - m);
    return (State){ m, x.l * ex + y.l * ey, x.a * ex + y.a * ey };
}

static State one(double s, double v) { return (State){ s, 1, v }; }

int main(void)
{
    enum { N = 1000, B = 32, NB = (N + B - 1) / B };
    double s[N], v[N];
    for (int i = 0; i < N; i++) { s[i] = 8 * sin(0.37 * i * i); v[i] = cos(0.11 * i); }

    State chunk[NB];                            /* one state per chunk of B keys */
    for (int c = 0; c < NB; c++) {
        chunk[c] = (State){ -INFINITY, 0, 0 };
        for (int i = c * B; i < N && i < (c + 1) * B; i++) chunk[c] = merge(chunk[c], one(s[i], v[i]));
    }
    State fwd = chunk[0], bwd = chunk[NB - 1];
    for (int c = 1; c < NB; c++) fwd = merge(fwd, chunk[c]);
    for (int c = NB - 2; c >= 0; c--) bwd = merge(chunk[c], bwd);
    for (int w = 1; w < NB; w *= 2)             /* tree: as a parallel reduction would */
        for (int c = 0; c + w < NB; c += 2 * w) chunk[c] = merge(chunk[c], chunk[c + w]);

    double m = s[0], l = 0, a = 0;              /* two-pass reference */
    for (int i = 1; i < N; i++) m = fmax(m, s[i]);
    for (int i = 0; i < N; i++) { l += exp(s[i] - m); a += exp(s[i] - m) * v[i]; }
    printf("two-pass    o = %.15f\n", a / l);
    printf("left-right  o = %.15f\n", fwd.a / fwd.l);
    printf("right-left  o = %.15f\n", bwd.a / bwd.l);
    printf("tree        o = %.15f\n", chunk[0].a / chunk[0].l);
    printf("states agree on m: %g %g %g %g\n", m, fwd.m, bwd.m, chunk[0].m);
    return 0;
}
