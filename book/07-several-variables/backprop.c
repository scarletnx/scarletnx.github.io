#include <math.h>
#include <stdio.h>

/* Reverse-mode differentiation on a tape. Each node records its operation, its
   inputs (earlier nodes) and its value; one backward pass gives every partial. */
enum op { VAR, ADD, MUL, EXP, LOG, SIN };
static struct { enum op op; int a, b; double val, adj; } t[32];
static int n;

static int node(enum op op, int a, int b, double val)
{
    t[n].op = op; t[n].a = a; t[n].b = b; t[n].val = val; t[n].adj = 0;
    return n++;
}
static int var(double v)      { return node(VAR, -1, -1, v); }
static int add(int a, int b)  { return node(ADD, a, b, t[a].val + t[b].val); }
static int mul(int a, int b)  { return node(MUL, a, b, t[a].val * t[b].val); }
static int exp_(int a)        { return node(EXP, a, -1, exp(t[a].val)); }
static int log_(int a)        { return node(LOG, a, -1, log(t[a].val)); }
static int sin_(int a)        { return node(SIN, a, -1, sin(t[a].val)); }

static void backward(int out)
{
    t[out].adj = 1;                              /* d out / d out */
    for (int i = out; i >= 0; i--) {            /* reverse order of creation */
        double g = t[i].adj;
        int a = t[i].a, b = t[i].b;
        switch (t[i].op) {
        case VAR: break;
        case ADD: t[a].adj += g; t[b].adj += g; break;
        case MUL: t[a].adj += g * t[b].val; t[b].adj += g * t[a].val; break;
        case EXP: t[a].adj += g * t[i].val; break;        /* (e^u)' = e^u */
        case LOG: t[a].adj += g / t[a].val; break;        /* (ln u)' = 1/u */
        case SIN: t[a].adj += g * cos(t[a].val); break;
        }
    }
}

/* f(x, y, z) = log(e^(xy) + e^z) * sin x */
static double f(double x, double y, double z) { return log(exp(x * y) + exp(z)) * sin(x); }

int main(void)
{
    double in[3] = { 0.7, 1.3, 0.4 }, h = 1e-6;
    n = 0;
    int x = var(in[0]), y = var(in[1]), z = var(in[2]);
    int out = mul(log_(add(exp_(mul(x, y)), exp_(z))), sin_(x));
    backward(out);

    double a = exp(in[0] * in[1]) / (exp(in[0] * in[1]) + exp(in[2]));   /* by hand */
    double L = log(exp(in[0] * in[1]) + exp(in[2])), s = sin(in[0]);
    double hand[3] = { a * in[1] * s + L * cos(in[0]), a * in[0] * s, (1 - a) * s };
    printf("f = %.12f (%d nodes)\n", t[out].val, n);
    for (int i = 0; i < 3; i++) {
        double p[3] = { in[0], in[1], in[2] }, m[3] = { in[0], in[1], in[2] };
        p[i] += h; m[i] -= h;
        double fd = (f(p[0], p[1], p[2]) - f(m[0], m[1], m[2])) / (2 * h);
        printf("d/d%c: reverse %.12f  central diff %.12f  by hand %.12f\n",
               "xyz"[i], t[i].adj, fd, hand[i]);
    }
    return 0;
}
