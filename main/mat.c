//
//  mat.c
//  opticalflow
//
//  Created by Bao on 31/8/23.
//

#include "mat.h"
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <dspm_mult.h>
#include <dsps_add.h>

#define MAX_NUM_MATRICES 16

matrix_t g_matrices[MAX_NUM_MATRICES];
matrix_t g_filters[5];

int g_matrix_addr = 0;

matrix_t* filter_hori(void) {
    matrix_t *mat = &g_filters[0];
    mat->w = 2;
    mat->h = 2;
    mat->buf = (float*) malloc(mat->w*mat->h*sizeof(float));
    mat->buf[0] = -1.0/4;
    mat->buf[1] = 1.0/4;
    mat->buf[2] = -1.0/4;
    mat->buf[3] = 1.0/4;
    return mat;
}

matrix_t* filter_vert(void) {
    matrix_t *mat = &g_filters[1];
    mat->w = 2;
    mat->h = 2;
    mat->buf = (float*) malloc(mat->w*mat->h*sizeof(float));
    mat->buf[0] = -1.0/4;
    mat->buf[1] = -1.0/4;
    mat->buf[2] = 1.0/4;
    mat->buf[3] = 1.0/4;
    return mat;
}

matrix_t* filter_prev(void) {
    matrix_t *mat = &g_filters[2];
    mat->w = 2;
    mat->h = 2;
    mat->buf = (float*) malloc(mat->w*mat->h*sizeof(float));
    mat->buf[0] = -1.0/4;
    mat->buf[1] = -1.0/4;
    mat->buf[2] = -1.0/4;
    mat->buf[3] = -1.0/4;
    return mat;
}

matrix_t* filter_curr(void) {
    matrix_t *mat = &g_filters[3];
    mat->w = 2;
    mat->h = 2;
    mat->buf = (float*) malloc(mat->w*mat->h*sizeof(float));
    mat->buf[0] = 1.0/4;
    mat->buf[1] = 1.0/4;
    mat->buf[2] = 1.0/4;
    mat->buf[3] = 1.0/4;
    return mat;
}

matrix_t* mat_alloc(void) {
    if (g_matrix_addr >= MAX_NUM_MATRICES) {
        printf("Matrix alloc failed\n");
        return NULL;
    }
    
    matrix_t *mat = &g_matrices[g_matrix_addr];
    g_matrix_addr += 1;
    return mat;
}

matrix_t* mat_create(const uint8_t *frame, uint16_t height, uint16_t width) {
    matrix_t* mat = mat_alloc();
    if (mat != NULL) {
        mat->h = height;
        mat->w = width;
        
        mat->buf = (float*) malloc(mat->w*mat->h*sizeof(float));
        if (mat->buf == NULL) {
          printf("Fail to allocate memory %d\n", mat->w*mat->h*sizeof(float));
          return NULL;
        }

        if (frame != NULL) {
            mat_set(mat, frame);
        }
        else {
            memset(mat->buf, 0, mat->h*mat->w*sizeof(float));
        }
    }

    return mat;
}

void mat_set(matrix_t* mat, const uint8_t *frame) {
    if (frame == NULL) {
        printf("No set for a null frame\n");
        return;
    }

    for (int i = 0; i < mat->h*mat->w; i += 1) {
        mat->buf[i] = frame[i];
    }
}

void mat_print(const matrix_t* mat) {
    int m = mat->h;
    int n = mat->w;

    const float *C = mat->buf;
    for (int i = 0; i < m; i++) {
        for(int j = 0; j < n; j++) {
            printf("%d ", (int)floor(C[i * n + j]*10));
        }
        printf("\n");
    }
}

void mat_inv2x2(matrix_t *rmat) {
    if (rmat->h != 2 || rmat->w != 2) {
        printf("Input matrix size has to be 2x2\n");
        return;
    }
    
    float a = rmat->buf[0];
    float b = rmat->buf[1];
    float c = rmat->buf[2];
    float d = rmat->buf[3];
    float e = a*d - b*c;
    if (e == 0) {
        printf("Can not inverse the 2x2 matrix\n");
        return;
    }
    
    e = 1/e;
    rmat->buf[0] = d*e;
    rmat->buf[1] = -b*e;
    rmat->buf[2] = -c*e;
    rmat->buf[3] = a*e;
}

void mat_trans(const matrix_t *mat, matrix_t *rmat) {
    int m = mat->h;
    int n = mat->w;
    
    if (rmat->h != n || rmat->w != m) {
        printf("Transpose error %d %d\n", rmat->h, rmat->w);
    }
    
    const float *A = mat->buf;
    float *B = rmat->buf;
    
    for (int i = 0; i < m; i++) {
        for (int j = 0; j < n; j++) {
            B[m * j + i] = A[i * n + j];
        }
    }
}

void mat_flatten(matrix_t *rmat) {
    rmat->h = rmat->h*rmat->w;
    rmat->w = 1;
}

void mat_stack(const matrix_t *mat1, const matrix_t *mat2, matrix_t *rmat) {
    int m = mat1->h;
    int n = mat1->w;
    int p = mat2->w;
    
    if (m != mat2->h) {
        printf("Concatenting 2 different number of rows\n");
        return;
    }
    
    if (m != rmat->h || n + p != rmat->w) {
        printf("Invalid output matrix when concatenating\n");
    }
    
    const float *A = mat1->buf;
    const float *B = mat2->buf;
    float *C = rmat->buf;
    
    for (int i = 0; i < m; i += 1) {
        for (int j = 0; j < n; j += 1) {
            C[i * (n + p) + j] = A[i * n + j];
        }
        for (int j = 0; j < p; j += 1) {
            C[i * (n + p) + n + j] = B[i * p + j];
        }
    }
}

void mat_add(const matrix_t *mat1, const matrix_t *mat2, matrix_t *rmat) {
    int m = mat1->h;
    int n = mat1->w;
    if (m != mat2->h || n != mat2->w) {
        printf("Adding 2 different matrix sizes\n");
        return;
    }
    
    const float *A = mat1->buf;
    const float *B = mat2->buf;
    float *C = rmat->buf;

    dsps_add_f32_ansi(A, B, C, m * n, 1, 1, 1);
    
    // for (int i = 0; i < m; i++) {
    //     for(int j = 0; j < n; j++) {
    //         C[i * n + j] = A[i * n + j] + B[i * n + j];
    //     }
    // }
}

void mat_negative(const matrix_t *mat1, matrix_t *rmat) {
    int m = mat1->h;
    int n = mat1->w;
    const float *A = mat1->buf;
    float *B = rmat->buf;
    
    for (int i = 0; i < m; i++) {
        for(int j = 0; j < n; j++) {
            B[i * n + j] = - A[i * n + j];
        }
    }
}

void mat_dot(const matrix_t *mat1, const matrix_t *mat2, matrix_t *rmat) {
    int m = mat1->h;
    int p = mat1->w;
    int n = mat2->w;
    
    if (p != mat2->h) {
        printf("Multiplying 2 invalid matrix sizes\n");
        return;
    }
    
    const float *A = mat1->buf;
    const float *B = mat2->buf;
    float *C = rmat->buf;

    dspm_mult_f32_ansi(A, B, C, m, p, n);
    
    // for (int i = 0; i < m; i++) {
    //     for (int j = 0; j < n; j++) {
    //         C[i * n + j] = 0;
    //         for (int k = 0; k < p; k++) {
    //             C[i * n + j] += A[p * i + k] * B[n * k + j];
    //         }
    //     }
    // }
}

void mat_conv(const matrix_t *mat, const matrix_t *filter, matrix_t *rmat) {
    int m = mat->h;
    int n = mat->w;
    
    const float *A = mat->buf;
    const float *B = filter->buf;
    float *C = rmat->buf;
    
    // Convolve valid area
    for (int i = 0; i < m - 1; i++) {
        for (int j = 0; j < n - 1; j++) {
            C[i * n + j] = 0;
            for (int fi = 0; fi < filter->h; fi++) {
                for (int fj = 0; fj < filter->w; fj++) {
                    C[i * n + j] += A[(i+fi) * n + (j+fj)] * B[fi * filter->w + fj];
                }
            }
        }
    }

    // Zero out the last row and column (edges)
    for (int j = 0; j < n; j++) {
        C[(m - 1) * n + j] = 0; // Last row
    }
    for (int i = 0; i < m; i++) {
        C[i * n + (n - 1)] = 0; // Last column
    }
}

void mat_reset_all(void) {
    for (int i = 0; i < g_matrix_addr; i++) {
        if (g_matrices[i].buf != NULL) {
            free(g_matrices[i].buf);
            g_matrices[i].buf = NULL;
        }
    }
    g_matrix_addr = 0;
    
    // Also free filters if they were allocated (they use g_filters, not g_matrices)
    for (int i = 0; i < 5; i++) {
        if (g_filters[i].buf != NULL) {
            free(g_filters[i].buf);
            g_filters[i].buf = NULL;
        }
    }
}
