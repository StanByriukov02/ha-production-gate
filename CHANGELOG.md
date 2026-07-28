# Changelog

## 0.2.1 — 2026-07-28

Product cells T1–T5 on the public Gate face.

### T5 — thin ros2 Dual
- `ha-dual-ros2` — URDF path **or** `robot_description` XML → Dual
- ament package `ros2/ha_dual_ros2` (optional `rclpy` node · launch)
- Example 10 · CI smoke without Gazebo stack

### Earlier in 0.2.x (held)
- T1 URDF contact extract · T2 desk stand log · T3 soils workbench · T4 private dogfood (B)

## 0.2.0 — 2026-07-27

Dogfood update: owned Dual inputs, stranger boards, desk truth UX.

### Product
- `ha-dual-socket --soils` — owned Safe/Hostile JSON + contact on the board
- Example 08 — skid URDF Dual split (owned soil ids)
- Example 09 — third-party Fetch URDF · **FAIL is Gate truth** (PASS not required)
- Boards log ×5 under `docs/examples/boards_log_20260727/`

### Desk (minimal UX)
- Upload URDF **and** optional soils JSON
- Contact + soil ids on the result
- FAIL styled as valid Gate answer, not a broken demo
- v0.2 brand line

### Face
- README leads with Example 08 table
- CI expects Fetch FAIL as intentional

## 0.1.0 — 2026-07-26

Initial public soft Gate: Dual ritual, socket presets, local desk, Rust oracle bins.
