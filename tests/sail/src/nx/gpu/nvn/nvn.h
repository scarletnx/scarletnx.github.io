/* SPDX-License-Identifier: MIT
   SPDX-FileCopyrightText: 2020 h1k421
   Cut from ScarletNX's nvn.h (h1k421's reconstruction, MIT) for tests/check-manual.sh */

#pragma once

typedef uint8_t NVNboolean;

typedef struct {
    char reserved[0x3000];
} NVNdevice;

typedef struct {
    char reserved[0xA0];
} NVNcommandBuffer;

typedef struct {
    char reserved[0x80];
} NVNtextureBuilder;

/* the Ounce's objects (API 231): the bytes its driver uses */
typedef struct {
    char reserved[0xC8];
} NVNdlssParameters;

typedef enum {
    NVN_DEPTH_MODE_NEAR_IS_MINUS_W = 0x0,
    NVN_DEPTH_MODE_NEAR_IS_ZERO = 0x1,

    NVN_DEPTH_MODE_LARGE = 0x7FFFFFFF
} NVNdepthMode;

typedef enum {
#define NVN_TIC_FORMAT(i, p0, p1, p2, p3, p4, name) NVN_FORMAT_##name = i,
#include "nx/gpu/nvn/nvn_tic_format.inc"
    NVN_FORMAT_LARGE = 0x7FFFFFFF
} NVNformat;

typedef enum {
    NVN_SHADER_STAGE_VERTEX = 0x0,
    NVN_SHADER_STAGE_FRAGMENT = 0x1,
    NVN_SHADER_STAGE_GEOMETRY = 0x2,
    NVN_SHADER_STAGE_TESS_CONTROL = 0x3,
    NVN_SHADER_STAGE_TESS_EVALUATION = 0x4,
    NVN_SHADER_STAGE_COMPUTE = 0x5,
    /* the Ounce's (API 231), as its control sections number them (nvn_section.h) */
    NVN_SHADER_STAGE_TASK = 0x6,
    NVN_SHADER_STAGE_MESH = 0x7,

    NVN_SHADER_STAGE_LARGE = 0x7FFFFFFF
} NVNshaderStage;

typedef void (*PFNNVNGENERICFUNCPTRPROC)(void);
