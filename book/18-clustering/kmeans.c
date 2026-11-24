/* Lloyd's algorithm on 90 points in the plane, 3 clusters.
   Assign each point to the nearest center; move each center to the mean
   of its points; repeat until nothing moves. */
#include <math.h>
#include <stdio.h>
#include <stdlib.h>

#define N 90
#define K 3

static double gauss(void)
{
    double u = (rand() + 1.0) / (RAND_MAX + 2.0), v = (rand() + 1.0) / (RAND_MAX + 2.0);
    return sqrt(-2 * log(u)) * cos(6.283185307179586 * v);
}

int main(int argc, char **argv)
{
    double x[N][2], c[K][2], blob[K][2] = { { 1, 1 }, { 4, 1.5 }, { 2.5, 4 } };
    int a[N];
    srand(4);
    for (int i = 0; i < N; i++)
        for (int j = 0; j < 2; j++) x[i][j] = blob[i % K][j] + 0.6 * gauss();
    for (int k = 0; k < K; k++) {   /* a bad start: 3 points of the same blob */
        c[k][0] = x[3 * k][0]; c[k][1] = x[3 * k][1];
    }

    for (int it = 1, moved = 1; moved; it++) {
        double sse = 0, sum[K][2] = { { 0 } };
        int n[K] = { 0 };
        moved = 0;
        for (int i = 0; i < N; i++) {                  /* assignment step */
            int best = 0;
            double bd = INFINITY;
            for (int k = 0; k < K; k++) {
                double d = pow(x[i][0] - c[k][0], 2) + pow(x[i][1] - c[k][1], 2);
                if (d < bd) { bd = d; best = k; }
            }
            if (it == 1 || a[i] != best) moved = 1;
            a[i] = best;
            sse += bd;
            sum[best][0] += x[i][0]; sum[best][1] += x[i][1]; n[best]++;
        }
        printf("iteration %d: sum of squared distances %.4f, sizes %d %d %d\n",
               it, sse, n[0], n[1], n[2]);
        for (int k = 0; k < K; k++)                    /* update step */
            if (n[k]) { c[k][0] = sum[k][0] / n[k]; c[k][1] = sum[k][1] / n[k]; }
    }
    for (int k = 0; k < K; k++) printf("center %d: (%.3f, %.3f)\n", k, c[k][0], c[k][1]);
    if (argc > 1) {                                    /* points for the figure */
        FILE *f = fopen(argv[1], "w");
        if (!f) return 1;
        for (int i = 0; i < N; i++) fprintf(f, "%.3f %.3f %d\n", x[i][0], x[i][1], a[i]);
        for (int k = 0; k < K; k++) fprintf(f, "%.3f %.3f c\n", c[k][0], c[k][1]);
        fclose(f);
    }
    return 0;
}
