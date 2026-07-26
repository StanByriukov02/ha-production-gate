//! Serial revolute chain — SE(3) FK with arbitrary joint axes (appendage OS crown).

use serde::{Deserialize, Serialize};

use crate::cga_rotor3::{Rotor3, Vec3};
use crate::lie_se3_step::Motor7;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Se3JointSpec {
    #[serde(default = "default_revolute")]
    pub joint_type: String,
    pub origin_xyz: [f64; 3],
    pub origin_rpy: [f64; 3],
    pub axis_xyz: [f64; 3],
    /// When true, `origin_xyz` is link extent applied in the frame after joint rotation (planar degenerate).
    #[serde(default)]
    pub link_in_child_frame: bool,
}

fn default_revolute() -> String {
    "revolute".into()
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Se3ChainParams {
    pub joints: Vec<Se3JointSpec>,
}

impl Se3ChainParams {
    pub fn n(&self) -> usize {
        self.joints.len()
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Se3FkReport {
    pub ee_x: f64,
    pub ee_y: f64,
    pub ee_z: f64,
    pub qw: f64,
    pub qx: f64,
    pub qy: f64,
    pub qz: f64,
    pub backend_id: String,
}

fn normalize_axis(a: [f64; 3]) -> Vec3 {
    let n = (a[0] * a[0] + a[1] * a[1] + a[2] * a[2]).sqrt().max(1e-12);
    Vec3::new(a[0] / n, a[1] / n, a[2] / n)
}

fn rotor_from_rpy(roll: f64, pitch: f64, yaw: f64) -> Rotor3 {
    let cr = (roll * 0.5).cos();
    let sr = (roll * 0.5).sin();
    let cp = (pitch * 0.5).cos();
    let sp = (pitch * 0.5).sin();
    let cy = (yaw * 0.5).cos();
    let sy = (yaw * 0.5).sin();
    let qw = cr * cp * cy + sr * sp * sy;
    let qx = sr * cp * cy - cr * sp * sy;
    let qy = cr * sp * cy + sr * cp * sy;
    let qz = cr * cp * sy - sr * sp * cy;
    Rotor3 {
        s: qw,
        b12: qx,
        b23: qy,
        b31: qz,
    }
    .normalize()
}

pub fn se3_motor_identity() -> Motor7 {
    Motor7 {
        qw: 1.0,
        qx: 0.0,
        qy: 0.0,
        qz: 0.0,
        tx: 0.0,
        ty: 0.0,
        tz: 0.0,
    }
}

fn motor_from_rotor_t(r: Rotor3, t: (f64, f64, f64)) -> Motor7 {
    Motor7 {
        qw: r.s,
        qx: r.b12,
        qy: r.b23,
        qz: r.b31,
        tx: t.0,
        ty: t.1,
        tz: t.2,
    }
}

fn rotate_vector(r: Rotor3, v: Vec3) -> Vec3 {
    let rv = Rotor3 {
        s: 0.0,
        b12: v.x,
        b23: v.y,
        b31: v.z,
    };
    let out = r.mul(rv).mul(r.reverse());
    Vec3::new(out.b12, out.b23, out.b31)
}

pub fn se3_compose_motors(a: Motor7, b: Motor7) -> Motor7 {
    let ra = Rotor3 {
        s: a.qw,
        b12: a.qx,
        b23: a.qy,
        b31: a.qz,
    };
    let rb = Rotor3 {
        s: b.qw,
        b12: b.qx,
        b23: b.qy,
        b31: b.qz,
    };
    let r = ra.mul(rb).normalize();
    let tb = Vec3::new(b.tx, b.ty, b.tz);
    let ta = Vec3::new(a.tx, a.ty, a.tz);
    let t_rot = rotate_vector(ra, tb);
    motor_from_rotor_t(
        r,
        (ta.x + t_rot.x, ta.y + t_rot.y, ta.z + t_rot.z),
    )
}

pub fn se3_joint_motion_motor(spec: &Se3JointSpec, q: f64) -> Motor7 {
    let r_origin = rotor_from_rpy(
        spec.origin_rpy[0],
        spec.origin_rpy[1],
        spec.origin_rpy[2],
    );
    let axis = normalize_axis(spec.axis_xyz);
    if spec.joint_type == "prismatic" {
        let tx = spec.origin_xyz[0] + axis.x * q;
        let ty = spec.origin_xyz[1] + axis.y * q;
        let tz = spec.origin_xyz[2] + axis.z * q;
        return motor_from_rotor_t(r_origin, (tx, ty, tz));
    }
    let r_joint = Rotor3::from_axis_angle(axis, q);
    let r = r_origin.mul(r_joint).normalize();
    let off = Vec3::new(spec.origin_xyz[0], spec.origin_xyz[1], spec.origin_xyz[2]);
    let t = if spec.link_in_child_frame {
        rotate_vector(r, off)
    } else {
        off
    };
    motor_from_rotor_t(r, (t.x, t.y, t.z))
}

pub fn se3_motor_to_fk_report(pose: Motor7, backend_id: &str) -> Se3FkReport {
    Se3FkReport {
        ee_x: pose.tx,
        ee_y: pose.ty,
        ee_z: pose.tz,
        qw: pose.qw,
        qx: pose.qx,
        qy: pose.qy,
        qz: pose.qz,
        backend_id: backend_id.into(),
    }
}

/// Forward kinematics — serial chain, revolute joints, URDF-style origins.
pub fn forward_kinematics_se3(params: &Se3ChainParams, q: &[f64]) -> Se3FkReport {
    let n = params.n();
    assert_eq!(q.len(), n, "q len must match joint count");
    let mut pose = se3_motor_identity();
    for (i, spec) in params.joints.iter().enumerate() {
        pose = se3_compose_motors(pose, se3_joint_motion_motor(spec, q[i]));
    }
    se3_motor_to_fk_report(pose, "serial_chain_se3_fk_v1")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn lc2_hip_y_axis() {
        let params = Se3ChainParams {
            joints: vec![Se3JointSpec {
                joint_type: "revolute".into(),
                origin_xyz: [0.0, 0.0, 0.035],
                origin_rpy: [0.0, 0.0, 0.0],
                axis_xyz: [0.0, 1.0, 0.0],
                link_in_child_frame: false,
            }],
        };
        let fk = forward_kinematics_se3(&params, &[0.35_f64]);
        assert!((fk.ee_x).abs() < 1e-6);
        assert!((fk.ee_y).abs() < 1e-6);
        assert!((fk.ee_z - 0.035).abs() < 1e-6);
    }

    #[test]
    fn prismatic_slide_z() {
        let params = Se3ChainParams {
            joints: vec![Se3JointSpec {
                joint_type: "prismatic".into(),
                origin_xyz: [0.0, 0.0, 0.1],
                origin_rpy: [0.0, 0.0, 0.0],
                axis_xyz: [0.0, 0.0, 1.0],
                link_in_child_frame: false,
            }],
        };
        let fk = forward_kinematics_se3(&params, &[0.05]);
        assert!((fk.ee_z - 0.15).abs() < 1e-6);
    }

    #[test]
    fn planar_scout_parity_child_frame_links() {
        use crate::serial_arm_planar::{forward_kinematics, SerialArmParams};

        let ll = [0.25_f64, 0.28, 0.22];
        let q = [0.35_f64, 0.42, -0.18];
        let planar = forward_kinematics(
            &SerialArmParams {
                link_lengths: ll.to_vec(),
                link_masses: vec![0.45, 0.38, 0.22],
                g: 1.62,
            },
            &q,
        );
        let params = Se3ChainParams {
            joints: ll
                .iter()
                .map(|&l| Se3JointSpec {
                    joint_type: "revolute".into(),
                    origin_xyz: [l, 0.0, 0.0],
                    origin_rpy: [0.0, 0.0, 0.0],
                    axis_xyz: [0.0, 0.0, 1.0],
                    link_in_child_frame: true,
                })
                .collect(),
        };
        let se3 = forward_kinematics_se3(&params, &q);
        assert!((se3.ee_x - planar.ee_x).abs() < 1e-9);
        assert!((se3.ee_y - planar.ee_y).abs() < 1e-9);
        assert!(se3.ee_z.abs() < 1e-9);
    }
}
