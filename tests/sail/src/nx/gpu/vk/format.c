/* SPDX-License-Identifier: GPL-3.0-or-later
   Copyright 2026 the ScarletNX contributors */
/* Cut from ScarletNX's vk/format.c for tests/check-manual.sh: the three switches the NVN manual reads */

static VkFmt rt_format(u32 f) {
    switch (f) {
        case 0xC0:
        case 0xC3: return C(VK_FORMAT_R32G32B32A32_SFLOAT, 16, 0); /* the X formats: the fourth component is padding */
        case 0xC1:
        case 0xC4: return C(VK_FORMAT_R32G32B32A32_SINT, 16, 2);
        case 0xC2:
        case 0xC5: return C(VK_FORMAT_R32G32B32A32_UINT, 16, 1);
        case 0xC6: return C(VK_FORMAT_R16G16B16A16_UNORM, 8, 0);
        case 0xC7: return C(VK_FORMAT_R16G16B16A16_SNORM, 8, 0);
        case 0xC8: return C(VK_FORMAT_R16G16B16A16_SINT, 8, 2);
        case 0xC9: return C(VK_FORMAT_R16G16B16A16_UINT, 8, 1);
        case 0xCA:
        case 0xCE: return C(VK_FORMAT_R16G16B16A16_SFLOAT, 8, 0);
        case 0xCB: return C(VK_FORMAT_R32G32_SFLOAT, 8, 0);
        case 0xCC: return C(VK_FORMAT_R32G32_SINT, 8, 2);
        case 0xCD: return C(VK_FORMAT_R32G32_UINT, 8, 1);
        case 0xCF:
        case 0xE6: return Cbgra(VK_FORMAT_B8G8R8A8_UNORM);
        case 0xD0:
        case 0xE7: return Cbgra(VK_FORMAT_B8G8R8A8_SRGB);
        case 0xD1: return C(VK_FORMAT_A2B10G10R10_UNORM_PACK32, 4, 0);
        case 0xD2: return C(VK_FORMAT_A2B10G10R10_UINT_PACK32, 4, 1);
        case 0xD5:
        case 0xF9: return C(VK_FORMAT_R8G8B8A8_UNORM, 4, 0);
        case 0xD6:
        case 0xFA: return C(VK_FORMAT_R8G8B8A8_SRGB, 4, 0);
        case 0xD7: return C(VK_FORMAT_R8G8B8A8_SNORM, 4, 0);
        case 0xD8: return C(VK_FORMAT_R8G8B8A8_SINT, 4, 2);
        case 0xD9: return C(VK_FORMAT_R8G8B8A8_UINT, 4, 1);
        case 0xDA: return C(VK_FORMAT_R16G16_UNORM, 4, 0);
        case 0xDB: return C(VK_FORMAT_R16G16_SNORM, 4, 0);
        case 0xDC: return C(VK_FORMAT_R16G16_SINT, 4, 2);
        case 0xDD: return C(VK_FORMAT_R16G16_UINT, 4, 1);
        case 0xDE: return C(VK_FORMAT_R16G16_SFLOAT, 4, 0);
        case 0xDF: return Cbgra(VK_FORMAT_A2R10G10B10_UNORM_PACK32); /* B10G10R10A2: blue in the low bits */
        case 0xE0: return C(VK_FORMAT_B10G11R11_UFLOAT_PACK32, 4, 0);
        case 0xE3: return C(VK_FORMAT_R32_SINT, 4, 2);
        case 0xE4: return C(VK_FORMAT_R32_UINT, 4, 1);
        case 0xE5: return C(VK_FORMAT_R32_SFLOAT, 4, 0);
        case 0xE8: return C(VK_FORMAT_R5G6B5_UNORM_PACK16, 2, 0);
        case 0xE9: /* B5G5R5A1: blue in the low bits, alpha in the top one (Ryujinx's table) */
        case 0xF8: return C(VK_FORMAT_A1R5G5B5_UNORM_PACK16, 2, 0);
        case 0xEA: return C(VK_FORMAT_R8G8_UNORM, 2, 0);
        case 0xEB: return C(VK_FORMAT_R8G8_SNORM, 2, 0);
        case 0xEC: return C(VK_FORMAT_R8G8_SINT, 2, 2);
        case 0xED: return C(VK_FORMAT_R8G8_UINT, 2, 1);
        case 0xEE: return C(VK_FORMAT_R16_UNORM, 2, 0);
        case 0xEF: return C(VK_FORMAT_R16_SNORM, 2, 0);
        case 0xF0: return C(VK_FORMAT_R16_SINT, 2, 2);
        case 0xF1: return C(VK_FORMAT_R16_UINT, 2, 1);
        case 0xF2: return C(VK_FORMAT_R16_SFLOAT, 2, 0);
        case 0xF3: return C(VK_FORMAT_R8_UNORM, 1, 0);
        case 0xF4: return C(VK_FORMAT_R8_SNORM, 1, 0);
        case 0xF5: return C(VK_FORMAT_R8_SINT, 1, 2);
        case 0xF6: return C(VK_FORMAT_R8_UINT, 1, 1);
    }
    VkFmt r = {0};
    return r;
}

VkFmt vk_zt_format(u32 f) {
    switch (f) {
        case 0x0A: return D(VK_FORMAT_D32_SFLOAT, 4, 0);
        case 0x13: return D(VK_FORMAT_D16_UNORM, 2, 0);
        case 0x14:
        case 0x15:
        case 0x16:
        case 0x17: /* S8: only the stencil is used, a byte a texel in guest memory */
        case 0x18:
            /* D24S8 isn't supported everywhere (AMD), D32F S8 holds the same values. Their texels keep their size in
               guest memory, which is what bpp counts: 4 bytes, S8's 1 */
            return D(has_features(VK_FORMAT_D24_UNORM_S8_UINT, VK_FORMAT_FEATURE_DEPTH_STENCIL_ATTACHMENT_BIT)
                         ? VK_FORMAT_D24_UNORM_S8_UINT
                         : VK_FORMAT_D32_SFLOAT_S8_UINT,
                     f == 0x17 ? 1 : 4, 1);
        case 0x19: return D(VK_FORMAT_D32_SFLOAT_S8_UINT, 8, 1);
    }
    static u32 said[8];
    if (first_time(said, f)) WARN("vulkan: unsupported depth format %x, using D32F\n", f);
    return D(VK_FORMAT_D32_SFLOAT, 4, 0);
}

static VkFmt tic_format(u32 w0, int srgb, u32 native) {
    u32 f = w0 & 0x7F, ct = (w0 >> 7) & 7;
    int flt = ct == 7, sn = ct == 1, ui = ct == 4, si = ct == 3;
    u32 etc2 = native & NATIVE_ETC2, bc = native & NATIVE_BC; /* sampled as blocks (TE) */
    u32 as_astc = native & BCN_AS_ASTC, bc1_astc = native & BC1_AS_ASTC;
    const VkFormat astc4 = srgb ? VK_FORMAT_ASTC_4x4_SRGB_BLOCK : VK_FORMAT_ASTC_4x4_UNORM_BLOCK, no = VK_FORMAT_UNDEFINED;
#define PICK(F_, SN_, UI_, SI_, UN_, bpp_)                                                                             \
    return flt  ? T(F_, bpp_, 0, 0)                                                                                    \
           : sn ? T(SN_, bpp_, 0, 0)                                                                                   \
           : ui ? T(UI_, bpp_, 1, 0)                                                                                   \
           : si ? T(SI_, bpp_, 1, 1)                                                                                   \
                : T(UN_, bpp_, 0, 0)
    switch (f) {
        case 0x01:
            return flt  ? T(VK_FORMAT_R32G32B32A32_SFLOAT, 16, 0, 0)
                   : ui ? T(VK_FORMAT_R32G32B32A32_UINT, 16, 1, 0)
                        : T(VK_FORMAT_R32G32B32A32_SINT, 16, 1, 1);
        case 0x02: return TV(VK_FORMAT_R32G32B32A32_SFLOAT, 12, VKC_RGB32F);
        case 0x03:
            PICK(VK_FORMAT_R16G16B16A16_SFLOAT, VK_FORMAT_R16G16B16A16_SNORM, VK_FORMAT_R16G16B16A16_UINT,
                 VK_FORMAT_R16G16B16A16_SINT, VK_FORMAT_R16G16B16A16_UNORM, 8);
        case 0x04:
            return flt  ? T(VK_FORMAT_R32G32_SFLOAT, 8, 0, 0)
                   : ui ? T(VK_FORMAT_R32G32_UINT, 8, 1, 0)
                        : T(VK_FORMAT_R32G32_SINT, 8, 1, 1);
        case 0x07:
        case 0x08:
            if (!flt && !sn && !ui && !si) return T(srgb ? VK_FORMAT_R8G8B8A8_SRGB : VK_FORMAT_R8G8B8A8_UNORM, 4, 0, 0);
            PICK(VK_FORMAT_R8G8B8A8_UNORM, VK_FORMAT_R8G8B8A8_SNORM, VK_FORMAT_R8G8B8A8_UINT, VK_FORMAT_R8G8B8A8_SINT,
                 VK_FORMAT_R8G8B8A8_UNORM, 4);
        case 0x09:
            return ui ? T(VK_FORMAT_A2B10G10R10_UINT_PACK32, 4, 1, 0) : T(VK_FORMAT_A2B10G10R10_UNORM_PACK32, 4, 0, 0);
        /* ETC2 to RGBA8; EAC's 11 bits to 16 bit channels, so none are lost */
        case 0x06:
            return TE(srgb ? VK_FORMAT_ETC2_R8G8B8_SRGB_BLOCK : VK_FORMAT_ETC2_R8G8B8_UNORM_BLOCK,
                      srgb ? VK_FORMAT_R8G8B8A8_SRGB : VK_FORMAT_R8G8B8A8_UNORM, 8, VKC_ETC2, etc2);
        case 0x0A:
            return TE(srgb ? VK_FORMAT_ETC2_R8G8B8A1_SRGB_BLOCK : VK_FORMAT_ETC2_R8G8B8A1_UNORM_BLOCK,
                      srgb ? VK_FORMAT_R8G8B8A8_SRGB : VK_FORMAT_R8G8B8A8_UNORM, 8, VKC_ETC2_PTA, etc2);
        case 0x0B:
            return TE(srgb ? VK_FORMAT_ETC2_R8G8B8A8_SRGB_BLOCK : VK_FORMAT_ETC2_R8G8B8A8_UNORM_BLOCK,
                      srgb ? VK_FORMAT_R8G8B8A8_SRGB : VK_FORMAT_R8G8B8A8_UNORM, 16, VKC_ETC2_RGBA, etc2);
        case 0x19:
            return sn ? TE(VK_FORMAT_EAC_R11_SNORM_BLOCK, VK_FORMAT_R16_SNORM, 8, VKC_EAC_R_SNORM, etc2)
                      : TE(VK_FORMAT_EAC_R11_UNORM_BLOCK, VK_FORMAT_R16_UNORM, 8, VKC_EAC_R, etc2);
        case 0x1A:
            return sn ? TE(VK_FORMAT_EAC_R11G11_SNORM_BLOCK, VK_FORMAT_R16G16_SNORM, 16, VKC_EAC_RG_SNORM, etc2)
                      : TE(VK_FORMAT_EAC_R11G11_UNORM_BLOCK, VK_FORMAT_R16G16_UNORM, 16, VKC_EAC_RG, etc2);
        case 0x0C:
            PICK(VK_FORMAT_R16G16_SFLOAT, VK_FORMAT_R16G16_SNORM, VK_FORMAT_R16G16_UINT, VK_FORMAT_R16G16_SINT,
                 VK_FORMAT_R16G16_UNORM, 4);
        case 0x0F:
            return flt  ? T(VK_FORMAT_R32_SFLOAT, 4, 0, 0)
                   : ui ? T(VK_FORMAT_R32_UINT, 4, 1, 0)
                        : T(VK_FORMAT_R32_SINT, 4, 1, 1);
        case 0x12: return TV(VK_FORMAT_R8G8B8A8_UNORM, 2, VKC_RGBA4); /* R in the low bits */
        case 0x13: return TV(VK_FORMAT_R8G8B8A8_UNORM, 2, VKC_A5B5G5R1);
        case 0x14: return TV(VK_FORMAT_R8G8B8A8_UNORM, 2, VKC_RGB5A1);
        case 0x15: return T(VK_FORMAT_B5G6R5_UNORM_PACK16, 2, 0, 0); /* R in the low bits */
        case 0x18:
            PICK(VK_FORMAT_R8G8_UNORM, VK_FORMAT_R8G8_SNORM, VK_FORMAT_R8G8_UINT, VK_FORMAT_R8G8_SINT,
                 VK_FORMAT_R8G8_UNORM, 2);
        case 0x1B:
            PICK(VK_FORMAT_R16_SFLOAT, VK_FORMAT_R16_SNORM, VK_FORMAT_R16_UINT, VK_FORMAT_R16_SINT, VK_FORMAT_R16_UNORM,
                 2);
        case 0x1C:
        case 0x1D:
            PICK(VK_FORMAT_R8_UNORM, VK_FORMAT_R8_SNORM, VK_FORMAT_R8_UINT, VK_FORMAT_R8_SINT, VK_FORMAT_R8_UNORM, 1);
        case 0x20: return T(VK_FORMAT_E5B9G9R9_UFLOAT_PACK32, 4, 0, 0);
        case 0x21: return T(VK_FORMAT_B10G11R11_UFLOAT_PACK32, 4, 0, 0);
        /* BCn as ASTC 4x4 where the GPU samples that (TB): BC1 (until memory runs short), BC2, BC3 and BC7. Else as ETC2
           and EAC where the GPU samples those: BC1 as RGB8A1, whose punch-through alpha is BC1's
           transparent black; BC2, BC3 and BC7 as RGBA8; BC4 and BC5 as R11 and RG11. Else to RGBA8, BC4 and BC5 to 16
           bit channels and BC6H to half floats, so their interpolants keep the precision a GPU decodes them in */
        case 0x24:
            return TB(srgb ? VK_FORMAT_BC1_RGBA_SRGB_BLOCK : VK_FORMAT_BC1_RGBA_UNORM_BLOCK, astc4,
                      srgb ? VK_FORMAT_ETC2_R8G8B8A1_SRGB_BLOCK : VK_FORMAT_ETC2_R8G8B8A1_UNORM_BLOCK,
                      srgb ? VK_FORMAT_R8G8B8A8_SRGB : VK_FORMAT_R8G8B8A8_UNORM, 8, VKC_BC1, bc, etc2, bc1_astc);
        case 0x25:
            return TB(srgb ? VK_FORMAT_BC2_SRGB_BLOCK : VK_FORMAT_BC2_UNORM_BLOCK, astc4,
                      srgb ? VK_FORMAT_ETC2_R8G8B8A8_SRGB_BLOCK : VK_FORMAT_ETC2_R8G8B8A8_UNORM_BLOCK,
                      srgb ? VK_FORMAT_R8G8B8A8_SRGB : VK_FORMAT_R8G8B8A8_UNORM, 16, VKC_BC2, bc, etc2, as_astc);
        case 0x26:
            return TB(srgb ? VK_FORMAT_BC3_SRGB_BLOCK : VK_FORMAT_BC3_UNORM_BLOCK, astc4,
                      srgb ? VK_FORMAT_ETC2_R8G8B8A8_SRGB_BLOCK : VK_FORMAT_ETC2_R8G8B8A8_UNORM_BLOCK,
                      srgb ? VK_FORMAT_R8G8B8A8_SRGB : VK_FORMAT_R8G8B8A8_UNORM, 16, VKC_BC3, bc, etc2, as_astc);
        case 0x27:
            return sn ? TB(VK_FORMAT_BC4_SNORM_BLOCK, no, VK_FORMAT_EAC_R11_SNORM_BLOCK, VK_FORMAT_R16_SNORM, 8,
                           VKC_BC4_SNORM, bc, etc2, as_astc)
                      : TB(VK_FORMAT_BC4_UNORM_BLOCK, no, VK_FORMAT_EAC_R11_UNORM_BLOCK, VK_FORMAT_R16_UNORM, 8, VKC_BC4,
                           bc, etc2, as_astc);
        case 0x28:
            return sn ? TB(VK_FORMAT_BC5_SNORM_BLOCK, no, VK_FORMAT_EAC_R11G11_SNORM_BLOCK, VK_FORMAT_R16G16_SNORM, 16,
                           VKC_BC5_SNORM, bc, etc2, as_astc)
                      : TB(VK_FORMAT_BC5_UNORM_BLOCK, no, VK_FORMAT_EAC_R11G11_UNORM_BLOCK, VK_FORMAT_R16G16_UNORM, 16,
                           VKC_BC5, bc, etc2, as_astc);
        case 0x17:
            return TB(srgb ? VK_FORMAT_BC7_SRGB_BLOCK : VK_FORMAT_BC7_UNORM_BLOCK, astc4,
                      srgb ? VK_FORMAT_ETC2_R8G8B8A8_SRGB_BLOCK : VK_FORMAT_ETC2_R8G8B8A8_UNORM_BLOCK,
                      srgb ? VK_FORMAT_R8G8B8A8_SRGB : VK_FORMAT_R8G8B8A8_UNORM, 16, VKC_BC7, bc, etc2, as_astc);
        case 0x10:
            return TB(VK_FORMAT_BC6H_SFLOAT_BLOCK, no, VK_FORMAT_UNDEFINED, VK_FORMAT_R16G16B16A16_SFLOAT, 16, VKC_BC6H_SF,
                      bc, etc2, as_astc);
        case 0x11:
            return TB(VK_FORMAT_BC6H_UFLOAT_BLOCK, no, VK_FORMAT_UNDEFINED, VK_FORMAT_R16G16B16A16_SFLOAT, 16, VKC_BC6H_UF,
                      bc, etc2, as_astc);
        case 0x40: return TA(4, 4, srgb, native);
        case 0x50: return TA(5, 4, srgb, native);
        case 0x41: return TA(5, 5, srgb, native);
        case 0x51: return TA(6, 5, srgb, native);
        case 0x42: return TA(6, 6, srgb, native);
        case 0x55: return TA(8, 5, srgb, native);
        case 0x52: return TA(8, 6, srgb, native);
        case 0x44: return TA(8, 8, srgb, native);
        case 0x56: return TA(10, 5, srgb, native);
        case 0x57: return TA(10, 6, srgb, native);
        case 0x53: return TA(10, 8, srgb, native);
        case 0x45: return TA(10, 10, srgb, native);
        case 0x54: return TA(12, 10, srgb, native);
        case 0x46: return TA(12, 12, srgb, native);
        /* depth and stencil, four bytes a texel in guest memory whatever the host depth format's size (texture.c
           unpacks each by where its depth bits are). G8R24 and G24R8 are a D24S8 target's two parts as color
           components, depth in 24 bits and stencil in 8: vk_tic_reads_stencil says which a header samples */
        case 0x0D:
        case 0x0E:
        case 0x29:
        case 0x2A:
        case 0x2B: {
            VkFmt r = vk_zt_format(0x14);
            r.raw = 0;
            r.conv = f == 0x0E || f == 0x29 ? VKC_S8D24 : f == 0x2A ? VKC_D24X8 : VKC_D24S8;
            return r;
        }
        case 0x2F: return vk_zt_format(0x0A);
        case 0x30: {
            VkFmt r = vk_zt_format(0x19); /* Zf32X24S8 (0x19 itself is EAC) */
            r.conv = VKC_D32S8;
            return r;
        }
        case 0x3A: return vk_zt_format(0x13);
    }
#undef PICK
    static u32 said[8];
    /* an empty header (word 0 nought) names no texture, not a format: the slots that read one say so, with its address
       and what they read in its place (vk_null_header_first) */
    if (w0 && first_time(said, f))
        WARN("vulkan: unsupported texture format %x, header word 0 %08x: no Vulkan format\n", f, w0);
    VkFmt r = {0};
    return r;
}
