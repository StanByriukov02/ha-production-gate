#include "ha_silicon_fuse.h"

#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <ctype.h>

#pragma pack(push, 1)
typedef struct {
    char magic[8];      /* "HAFUSE01" */
    uint32_t version;   /* 1 */
    uint8_t blown;      /* 0 or 1 */
    uint8_t body_bound; /* 0 or 1 — pad holds body_sha256 */
    uint8_t reserved[2];
    uint32_t blow_count;
    int32_t lie_score_milli;
    uint8_t body_sha256[32]; /* raw digest when body_bound */
    uint8_t pad[8];
} ha_fuse_blob_t;
#pragma pack(pop)

static const char HA_MAGIC[8] = {'H', 'A', 'F', 'U', 'S', 'E', '0', '1'};

static int hex_nibble(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

static int parse_sha256_hex(const char *hex, uint8_t out[32]) {
    size_t i;
    if (!hex) return HA_FUSE_ERR_ARG;
    for (i = 0; i < 64; i++) {
        if (!isxdigit((unsigned char)hex[i])) return HA_FUSE_ERR_ARG;
    }
    if (hex[64] != '\0') return HA_FUSE_ERR_ARG;
    for (i = 0; i < 32; i++) {
        int hi = hex_nibble(hex[i * 2]);
        int lo = hex_nibble(hex[i * 2 + 1]);
        if (hi < 0 || lo < 0) return HA_FUSE_ERR_ARG;
        out[i] = (uint8_t)((hi << 4) | lo);
    }
    return HA_FUSE_OK;
}

static void sha256_to_hex(const uint8_t in[32], char out[65]) {
    static const char *digits = "0123456789abcdef";
    size_t i;
    for (i = 0; i < 32; i++) {
        out[i * 2] = digits[(in[i] >> 4) & 0xf];
        out[i * 2 + 1] = digits[in[i] & 0xf];
    }
    out[64] = '\0';
}

static void ha_fuse_init_blank(ha_fuse_blob_t *b) {
    memset(b, 0, sizeof(*b));
    memcpy(b->magic, HA_MAGIC, 8);
    b->version = 1;
    b->blown = 0;
    b->body_bound = 0;
    b->blow_count = 0;
    b->lie_score_milli = 0;
}

static int ha_fuse_read(const char *path, ha_fuse_blob_t *b) {
    FILE *f;
    size_t n;
    if (sizeof(ha_fuse_blob_t) != 64) {
        return HA_FUSE_ERR_MAGIC;
    }
    f = fopen(path, "rb");
    if (!f) {
        return HA_FUSE_ERR_IO;
    }
    n = fread(b, 1, sizeof(*b), f);
    fclose(f);
    if (n != sizeof(*b)) {
        return HA_FUSE_ERR_IO;
    }
    if (memcmp(b->magic, HA_MAGIC, 8) != 0 || b->version != 1) {
        return HA_FUSE_ERR_MAGIC;
    }
    if (b->blown > 1 || b->body_bound > 1) {
        return HA_FUSE_ERR_MAGIC;
    }
    /* Soft-OTP: blow_count without blown bit = hand-clear / tamper */
    if (b->blow_count > 0 && b->blown == 0) {
        return HA_FUSE_ERR_TAMPER;
    }
    return HA_FUSE_OK;
}

static int ha_fuse_write(const char *path, const ha_fuse_blob_t *b) {
    FILE *f = fopen(path, "wb");
    size_t n;
    if (!f) {
        return HA_FUSE_ERR_IO;
    }
    n = fwrite(b, 1, sizeof(*b), f);
    if (fclose(f) != 0 || n != sizeof(*b)) {
        return HA_FUSE_ERR_IO;
    }
    return HA_FUSE_OK;
}

int ha_fuse_ensure(const char *path) {
    ha_fuse_blob_t b;
    FILE *f;
    int rc;
    if (!path || !path[0]) {
        return HA_FUSE_ERR_ARG;
    }
    /* Create blank only when file is absent — never heal TAMPER/MAGIC by rewrite */
    f = fopen(path, "rb");
    if (!f) {
        ha_fuse_init_blank(&b);
        return ha_fuse_write(path, &b);
    }
    fclose(f);
    rc = ha_fuse_read(path, &b);
    if (rc == HA_FUSE_OK) {
        return HA_FUSE_OK;
    }
    return rc;
}

int ha_fuse_bind_body(const char *path, const char *sha256_hex) {
    ha_fuse_blob_t b;
    uint8_t digest[32];
    int rc;
    if (!path || !path[0] || !sha256_hex) {
        return HA_FUSE_ERR_ARG;
    }
    rc = parse_sha256_hex(sha256_hex, digest);
    if (rc != HA_FUSE_OK) {
        return rc;
    }
    rc = ha_fuse_ensure(path);
    if (rc != HA_FUSE_OK) {
        return rc;
    }
    rc = ha_fuse_read(path, &b);
    if (rc != HA_FUSE_OK) {
        return rc;
    }
    /* First bind locks digest — cannot silently swap body after bind */
    if (b.body_bound) {
        if (memcmp(b.body_sha256, digest, 32) != 0) {
            return HA_FUSE_ERR_BOUND;
        }
        return HA_FUSE_OK; /* idempotent same digest */
    }
    memcpy(b.body_sha256, digest, 32);
    b.body_bound = 1;
    return ha_fuse_write(path, &b);
}

int ha_fuse_current_gate(const char *path) {
    ha_fuse_blob_t b;
    int rc;
    if (!path || !path[0]) {
        return -HA_FUSE_ERR_ARG;
    }
    rc = ha_fuse_ensure(path);
    if (rc != HA_FUSE_OK) {
        return -rc;
    }
    rc = ha_fuse_read(path, &b);
    if (rc != HA_FUSE_OK) {
        return -rc;
    }
    /* 1 = current may flow, 0 = blocked (apoptosis blown) */
    return b.blown ? 0 : 1;
}

int ha_fuse_status_json(const char *path, char *out, size_t out_cap) {
    ha_fuse_blob_t b;
    double lie;
    int n;
    int gate;
    int rc;
    char hex[65];
    if (!path || !out || out_cap < 128) {
        return HA_FUSE_ERR_ARG;
    }
    rc = ha_fuse_ensure(path);
    if (rc != HA_FUSE_OK) {
        return rc;
    }
    rc = ha_fuse_read(path, &b);
    if (rc != HA_FUSE_OK) {
        return rc;
    }
    lie = ((double)b.lie_score_milli) / 1000.0;
    gate = b.blown ? 0 : 1;
    if (b.body_bound) {
        sha256_to_hex(b.body_sha256, hex);
        n = snprintf(
            out,
            out_cap,
            "{"
            "\"schema\":\"silicon_fuse_v1\","
            "\"blown\":%s,"
            "\"blow_count\":%u,"
            "\"lie_score\":%.6f,"
            "\"irreversible\":true,"
            "\"backend\":\"c_file_efuse\","
            "\"blob_bytes\":64,"
            "\"body_bound\":true,"
            "\"body_sha256\":\"%s\","
            "\"mmio\":{"
            "\"APOPTOSIS_FUSE\":%u,"
            "\"CURRENT_GATE\":%u"
            "},"
            "\"honesty\":{"
            "\"not_otp_silicon\":true,"
            "\"file_backed\":true,"
            "\"current_gate_blocks_actuation\":true,"
            "\"epsilon\":[\"ε_file_backed_efuse\",\"ε_mmio_sim_not_asic\",\"ε_soft_not_iron\"]"
            "}"
            "}",
            b.blown ? "true" : "false",
            (unsigned)b.blow_count,
            lie,
            hex,
            (unsigned)b.blown,
            (unsigned)gate);
    } else {
        n = snprintf(
            out,
            out_cap,
            "{"
            "\"schema\":\"silicon_fuse_v1\","
            "\"blown\":%s,"
            "\"blow_count\":%u,"
            "\"lie_score\":%.6f,"
            "\"irreversible\":true,"
            "\"backend\":\"c_file_efuse\","
            "\"blob_bytes\":64,"
            "\"body_bound\":false,"
            "\"mmio\":{"
            "\"APOPTOSIS_FUSE\":%u,"
            "\"CURRENT_GATE\":%u"
            "},"
            "\"honesty\":{"
            "\"not_otp_silicon\":true,"
            "\"file_backed\":true,"
            "\"current_gate_blocks_actuation\":true,"
            "\"epsilon\":[\"ε_file_backed_efuse\",\"ε_mmio_sim_not_asic\",\"ε_soft_not_iron\"]"
            "}"
            "}",
            b.blown ? "true" : "false",
            (unsigned)b.blow_count,
            lie,
            (unsigned)b.blown,
            (unsigned)gate);
    }
    if (n < 0 || (size_t)n >= out_cap) {
        return HA_FUSE_ERR_BUF;
    }
    return HA_FUSE_OK;
}

int ha_fuse_blow(const char *path, double lie_score) {
    ha_fuse_blob_t b;
    int32_t milli;
    int rc;
    if (!path || !path[0]) {
        return HA_FUSE_ERR_ARG;
    }
    rc = ha_fuse_ensure(path);
    if (rc != HA_FUSE_OK) {
        return rc;
    }
    rc = ha_fuse_read(path, &b);
    if (rc != HA_FUSE_OK) {
        return rc;
    }
    b.blown = 1;
    if (b.blow_count < 0xffffffffu) {
        b.blow_count += 1;
    }
    if (lie_score > 2147480.0) {
        lie_score = 2147480.0;
    }
    if (lie_score < 0.0) {
        lie_score = 0.0;
    }
    milli = (int32_t)(lie_score * 1000.0 + 0.5);
    b.lie_score_milli = milli;
    return ha_fuse_write(path, &b);
}
