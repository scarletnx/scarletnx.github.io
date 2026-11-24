#include <math.h>
#include <stdio.h>

typedef struct { double m, l, a; } State;

static State merge(State x, State y)
{
    if (x.l == 0) return y;
    double m = fmax(x.m, y.m), ex = exp(x.m - m), ey = exp(y.m - m);
    return (State){ m, x.l * ex + y.l * ey, x.a * ex + y.a * ey };
}

int main(void)
{
    enum { N = 1024, B = 32, NB = N / B };
    double s[N], v[N];
    for (int i = 0; i < N; i++) { s[i] = 8 * sin(0.37 * i * i); v[i] = cos(0.11 * i); }

    State st = { -INFINITY, 0, 0 };
    double num = 0, den = 0;                    /* the same thing written directly */
    for (int c = 0; c < NB; c++) {
        double sbar = 0, vbar = 0;
        for (int i = c * B; i < (c + 1) * B; i++) { sbar += s[i] / B; vbar += v[i] / B; }
        if (c % 4 == 0) {                       /* expanded: every key */
            for (int i = c * B; i < (c + 1) * B; i++) {
                st = merge(st, (State){ s[i], 1, v[i] });
                num += exp(s[i]) * v[i]; den += exp(s[i]);
            }
        } else {                                /* represented: (sbar, |C|, |C| vbar) */
            st = merge(st, (State){ sbar, B, B * vbar });
            num += B * exp(sbar) * vbar; den += B * exp(sbar);
        }
    }
    double l = 0, a = 0;
    for (int i = 0; i < N; i++) { l += exp(s[i]); a += exp(s[i]) * v[i]; }
    printf("mixed, merged states  %.15f\n", st.a / st.l);
    printf("mixed, written out    %.15f\n", num / den);
    printf("exact attention       %.15f\n", a / l);
    return 0;
}
