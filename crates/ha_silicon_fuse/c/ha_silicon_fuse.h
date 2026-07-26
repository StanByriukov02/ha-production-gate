/* ha_silicon_fuse — file-backed irreversible eFUSE (teaching SE toward silicon).
 * TABU: clear/unblow API. Once blown, stays blown for this fuse file.
 * current_gate: 1 = current may flow, 0 = apoptosis blocks actuation.
 */
#ifndef HA_SILICON_FUSE_H
#define HA_SILICON_FUSE_H

#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

#define HA_FUSE_OK 0
#define HA_FUSE_ERR_IO 1
#define HA_FUSE_ERR_MAGIC 2
#define HA_FUSE_ERR_ARG 3
#define HA_FUSE_ERR_BUF 4
#define HA_FUSE_ERR_TAMPER 5
#define HA_FUSE_ERR_BOUND 6

int ha_fuse_ensure(const char *path);
int ha_fuse_status_json(const char *path, char *out, size_t out_cap);
int ha_fuse_blow(const char *path, double lie_score);
/* Bind body SHA-256 (64 lowercase/upper hex). Does not clear blown. */
int ha_fuse_bind_body(const char *path, const char *sha256_hex);
/* 1 = current may flow, 0 = blocked, negative = -HA_FUSE_ERR_* */
int ha_fuse_current_gate(const char *path);

#ifdef __cplusplus
}
#endif

#endif /* HA_SILICON_FUSE_H */
