#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#define T 64                         /* tile: three 64 x 64 tiles of doubles = 96 KB */
#define MIN(a, b) ((a) < (b) ? (a) : (b))

static int n;
static double *A, *B, *C, *R;        /* n x n, row-major: A[i][k] is A[i*n + k] */

static void ijk(void)                /* textbook order: B is walked down a column */
{
    for (int i = 0; i < n; i++)
        for (int j = 0; j < n; j++) {
            double s = 0;
            for (int k = 0; k < n; k++) s += A[i*n + k] * B[k*n + j];
            C[i*n + j] = s;
        }
}

static void ikj(void)                /* same sums, inner loop along rows of B and C */
{
    memset(C, 0, sizeof *C * n * n);
    for (int i = 0; i < n; i++)
        for (int k = 0; k < n; k++)
            for (int j = 0; j < n; j++) C[i*n + j] += A[i*n + k] * B[k*n + j];
}

static void tiled(void)              /* ikj on T x T tiles that stay in cache */
{
    memset(C, 0, sizeof *C * n * n);
    for (int ii = 0; ii < n; ii += T)
        for (int kk = 0; kk < n; kk += T)
            for (int jj = 0; jj < n; jj += T)
                for (int i = ii; i < MIN(ii + T, n); i++)
                    for (int k = kk; k < MIN(kk + T, n); k++)
                        for (int j = jj; j < MIN(jj + T, n); j++)
                            C[i*n + j] += A[i*n + k] * B[k*n + j];
}

static void run(const char *name, void (*f)(void))
{
    clock_t t0 = clock();
    f();
    double s = (double)(clock() - t0) / CLOCKS_PER_SEC, err = 0;
    for (int i = 0; i < n * n; i++) err = fmax(err, fabs(C[i] - R[i]));
    printf("n = %d  %-5s %6.3f s  %5.2f GFLOP/s  max diff %.0e\n",
           n, name, s, 2.0 * n * n * n / s / 1e9, err);
}

static void bench(int size)
{
    n = size;
    A = malloc(sizeof *A * n * n); B = malloc(sizeof *B * n * n);
    C = malloc(sizeof *C * n * n); R = malloc(sizeof *R * n * n);
    srand(1);
    for (int i = 0; i < n * n; i++) {
        A[i] = rand() / (double)RAND_MAX;
        B[i] = rand() / (double)RAND_MAX;
    }
    ijk();
    memcpy(R, C, sizeof *C * n * n);  /* reference result */
    run("ijk", ijk);
    run("ikj", ikj);
    run("tiled", tiled);
    free(A); free(B); free(C); free(R);
}

int main(void)
{
    bench(1000);
    bench(1024);
    return 0;
}
