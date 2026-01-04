#include "optflow.h"
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <math.h>
#include "mat.h"

typedef struct {
    int w;
    int h;

    matrix_t *conv_x_prev;
    matrix_t *conv_y_prev;
    matrix_t *conv_t_prev;

    matrix_t *hfilter;
    matrix_t *vfilter;
    matrix_t *pfilter;
    matrix_t *cfilter;

    // Temp matrices for computation
    matrix_t *mframe;
    matrix_t *conv_x; // (h, w)
    matrix_t *conv_y; // (h, w)
    matrix_t *conv_t; // (h, w)
    matrix_t *Ix    ; // (h, w)
    matrix_t *Iy    ; // (h, w)
    matrix_t *It    ; // (h, w)
    matrix_t *A     ;
    matrix_t *AT    ;
    matrix_t *r1    ;
    matrix_t *r2    ;
    matrix_t *v     ;
} optflow_t;

optflow_t _optflow;

void optflow_init(uint16_t width, uint16_t height) {
    // Reset all matrices
    mat_reset_all();

    _optflow.w = width;
    _optflow.h = height;

    // Create a matrix with frame buffer
    _optflow.mframe = mat_create(NULL, _optflow.h, _optflow.w);

    // Create filters
    _optflow.hfilter = filter_hori();
    _optflow.vfilter = filter_vert();
    _optflow.pfilter = filter_prev();
    _optflow.cfilter = filter_curr();

    // Create zero matrix for previous frame
    _optflow.conv_x_prev = mat_create(NULL, _optflow.h, _optflow.w);
    _optflow.conv_y_prev = mat_create(NULL, _optflow.h, _optflow.w);
    _optflow.conv_t_prev = mat_create(NULL, _optflow.h, _optflow.w);

    _optflow.conv_x        = mat_create(NULL, _optflow.h, _optflow.w);
    _optflow.conv_y        = mat_create(NULL, _optflow.h, _optflow.w);
    _optflow.conv_t        = mat_create(NULL, _optflow.h, _optflow.w);
    _optflow.Ix            = mat_create(NULL, _optflow.h, _optflow.w);
    _optflow.Iy            = mat_create(NULL, _optflow.h, _optflow.w);
    _optflow.It            = mat_create(NULL, _optflow.h, _optflow.w);
    _optflow.A             = mat_create(NULL, _optflow.w*_optflow.h, 2);
    _optflow.AT            = mat_create(NULL, 2, _optflow.w*_optflow.h);
    _optflow.r1            = mat_create(NULL, 2, 2);
    _optflow.r2            = mat_create(NULL, 2, _optflow.w*_optflow.h);
    _optflow.v             = mat_create(NULL, 2, 1);

    // Cheat! Use memory order to remove matrix transpose AT
    _optflow.Ix->buf = _optflow.AT->buf;
    _optflow.Iy->buf = &_optflow.AT->buf[_optflow.h*_optflow.w];
}

void optflow_calc(uint8_t *frame, float *dx, float *dy, float *clearity) {
    // Set matrix buffer
    matrix_t *mframe = _optflow.mframe;
    mat_set(mframe, frame);

    // Temp matrices
    matrix_t *conv_x            = _optflow.conv_x      ;
    matrix_t *conv_y            = _optflow.conv_y      ;
    matrix_t *conv_t            = _optflow.conv_t      ;
    matrix_t *Ix                = _optflow.Ix          ;
    matrix_t *Iy                = _optflow.Iy          ;
    matrix_t *It                = _optflow.It          ;
    matrix_t *A                 = _optflow.A           ;
    matrix_t *AT                = _optflow.AT          ;
    matrix_t *r1                = _optflow.r1          ;
    matrix_t *r2                = _optflow.r2          ;
    matrix_t *v                 = _optflow.v           ;
                  
    // 1. Take horizontal derivatives
    mat_conv(mframe, _optflow.hfilter, conv_x);
    mat_conv(mframe, _optflow.vfilter, conv_y);
    mat_conv(mframe, _optflow.cfilter, conv_t);

    float sum = 0;
    for (int i = 0; i < _optflow.h; i++) {
        for (int j = 0; j < _optflow.w; j++) {
            sum += fabs(conv_x->buf[i + _optflow.w + j]) + fabs(conv_y->buf[i + _optflow.w + j]);
        }
    }

    *clearity = sum / (_optflow.h * _optflow.w);

    mat_add(_optflow.conv_x_prev, conv_x, Ix);
    mat_add(_optflow.conv_y_prev, conv_y, Iy);
    mat_add(_optflow.conv_t_prev, conv_t, It);

    _optflow.conv_x_prev = conv_x;
    _optflow.conv_y_prev = conv_y;
    mat_conv(mframe, _optflow.pfilter, _optflow.conv_t_prev);
      
    // 4. Compute b = -It
    mat_flatten(It); // (h*w, 1)

    // 5. Compute A, A transpose
    mat_flatten(Ix); // (h*w, 1)
    mat_flatten(Iy); // (h*w, 1)
    mat_stack(Ix, Iy, A); // (h*w, 2)
    // mat_trans(A, AT); // (2, h*w) // Cheat! AT = memory of Ix, Iy in order, so no need to transpose

    // 6. Compute (AT.A)^-1.AT.b
    mat_dot(AT, A, r1); // (2, 2)
    mat_inv2x2(r1);  // (2, 2)
    mat_dot(r1, AT, r2); // (2, h*w)
    mat_dot(r2, It, v); // (2, 1)
    float vx = v->buf[0];
    float vy = v->buf[1];
    
    *dx = vx;
    *dy = vy;
}

void get_roi(uint8_t *frame, int *x, int *y, int rw, int rh, int width, int height) {
    int h = (int)(height/rh);
    int w = (int)(width/rw);

    int max_clarity = 0;
    for (int i = 0; i < h; i += 1) {
        int ry = i * rh;
        for (int j = 0; j < w; j += 1) {
            int rx = j * rw;
            
            int block_sum = 0;
            for (int y = ry; y < ry + rh; y += 1) {
                for (int x = rx; x < rx + rw; x += 1) {
                    block_sum += frame[y*width + x];
                }
            }

            int block_avg = block_sum / (rh * rw);
            int clarity = 0;
            for (int y = ry; y < ry + rh; y += 1) {
                for (int x = rx; x < rx + rw; x += 1) {
                    clarity += abs(frame[y*width + x] - block_avg);
                }
            }

            if (clarity > max_clarity) {
                max_clarity = clarity;
                *y = i * rh;
                *x = j * rw;
            }
        }
    }
}

float get_clearity(uint8_t *frame, int width, int height) {
    int block_sum = 0;
    for (int i = 0; i < height; i += 1) {
        for (int j = 0; j < width; j += 1) {
            block_sum += frame[i*width + j];
        }
    }

    int block_avg = block_sum / (width * height);
    int clarity = 0;
    for (int i = 0; i < height; i += 1) {
        for (int j = 0; j < width; j += 1) {
            clarity += abs(frame[i*width + j] - block_avg);
        }
    }
    clarity = clarity / (width * height);

    return clarity / 128.0;
}
