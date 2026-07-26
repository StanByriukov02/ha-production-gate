//! JSON stdin/stdout — manipulator FK / IK / Jacobian / symplectic step crown.

use serde::{Deserialize, Serialize};
use std::io::{self, Read};

use universe_kinematic::serial_arm_planar::{
    forward_kinematics, fk_ik_roundtrip_error, grasp_force_step, inverse_kinematics_dls,
    jacobian_ee, symplectic_serial_arm_step, SerialArmParams, SerialArmState,
};
use universe_kinematic::serial_chain_se3::{forward_kinematics_se3, Se3ChainParams, Se3JointSpec};
use universe_kinematic::kinematic_tree_se3::{
    forward_kinematics_tree, inverse_kinematics_tree_position, KinematicTreeSpec, TreeJointSpec,
};
use std::collections::HashMap;

#[derive(Deserialize)]
struct Input {
    op: String,
    #[serde(default)]
    q: Vec<f64>,
    #[serde(default)]
    q_dot: Vec<f64>,
    #[serde(default)]
    link_lengths: Vec<f64>,
    #[serde(default)]
    link_masses: Vec<f64>,
    #[serde(default)]
    se3_joints: Vec<Se3JointInput>,
    #[serde(default)]
    tree_joints: Vec<TreeJointInput>,
    #[serde(default = "default_root_link")]
    root_link: String,
    #[serde(default)]
    target_link: String,
    #[serde(default)]
    q_by_name: HashMap<String, f64>,
    #[serde(default)]
    target_x: f64,
    #[serde(default)]
    target_y: f64,
    #[serde(default)]
    target_z: f64,
    #[serde(default)]
    torques: Vec<f64>,
    #[serde(default = "default_steps")]
    steps: usize,
    #[serde(default = "default_dt")]
    dt: f64,
    #[serde(default = "default_g")]
    g: f64,
    #[serde(default)]
    commanded_force_n: f64,
    #[serde(default)]
    allowed_max_force_n: f64,
    #[serde(default)]
    current_applied_force_n: f64,
    #[serde(default = "default_lever")]
    gripper_lever_arm_m: f64,
    #[serde(default = "default_ramp")]
    ramp_rate_n_per_s: f64,
}

#[derive(Deserialize)]
struct TreeJointInput {
    name: String,
    parent_link: String,
    child_link: String,
    #[serde(default = "default_revolute")]
    joint_type: String,
    #[serde(default)]
    origin_xyz: [f64; 3],
    #[serde(default)]
    origin_rpy: [f64; 3],
    #[serde(default = "default_axis_z")]
    axis_xyz: [f64; 3],
}

fn default_revolute() -> String {
    "revolute".into()
}

fn default_root_link() -> String {
    "base_link".into()
}

#[derive(Deserialize)]
struct Se3JointInput {
    #[serde(default = "default_revolute")]
    joint_type: String,
    #[serde(default)]
    origin_xyz: [f64; 3],
    #[serde(default)]
    origin_rpy: [f64; 3],
    #[serde(default = "default_axis_z")]
    axis_xyz: [f64; 3],
    #[serde(default)]
    link_in_child_frame: bool,
}

fn default_axis_z() -> [f64; 3] {
    [0.0, 0.0, 1.0]
}

fn default_steps() -> usize {
    1
}

fn default_dt() -> f64 {
    0.005
}
fn default_g() -> f64 {
    1.62
}
fn default_lever() -> f64 {
    0.04
}
fn default_ramp() -> f64 {
    200.0
}

fn params_from_input(inp: &Input) -> SerialArmParams {
    if !inp.link_lengths.is_empty() {
        let n = inp.link_lengths.len();
        let masses = if inp.link_masses.len() == n {
            inp.link_masses.clone()
        } else {
            vec![0.1; n]
        };
        return SerialArmParams {
            link_lengths: inp.link_lengths.clone(),
            link_masses: masses,
            g: inp.g,
        };
    }
    let mut p = SerialArmParams::scout_3dof_lunar();
    p.g = inp.g;
    p
}

fn default_q(n: usize) -> Vec<f64> {
    match n {
        1 => vec![0.35],
        2 => vec![0.3, 0.4],
        _ => vec![0.2, 0.3, -0.1],
    }
}

#[derive(Serialize)]
struct Output {
    verdict: String,
    op: String,
    report: serde_json::Value,
}

fn se3_params_from_input(inp: &Input) -> Se3ChainParams {
    let joints = inp
        .se3_joints
        .iter()
        .map(|j| Se3JointSpec {
            joint_type: j.joint_type.clone(),
            origin_xyz: j.origin_xyz,
            origin_rpy: j.origin_rpy,
            axis_xyz: j.axis_xyz,
            link_in_child_frame: j.link_in_child_frame,
        })
        .collect();
    Se3ChainParams { joints }
}

fn tree_spec_from_input(inp: &Input) -> KinematicTreeSpec {
    let joints = inp
        .tree_joints
        .iter()
        .map(|j| TreeJointSpec {
            name: j.name.clone(),
            parent_link: j.parent_link.clone(),
            child_link: j.child_link.clone(),
            joint_type: j.joint_type.clone(),
            origin_xyz: j.origin_xyz,
            origin_rpy: j.origin_rpy,
            axis_xyz: j.axis_xyz,
        })
        .collect();
    KinematicTreeSpec {
        root_link: inp.root_link.clone(),
        joints,
    }
}

fn main() {
    let mut buf = String::new();
    io::stdin().read_to_string(&mut buf).expect("stdin");
    let inp: Input = serde_json::from_str(&buf).expect("json");
    let params = params_from_input(&inp);
    let n = params.n();

    let (verdict, report): (String, serde_json::Value) = match inp.op.as_str() {
        "fk" => {
            let fk = forward_kinematics(&params, &inp.q);
            ("MANIPULATOR_FK_PASS".into(), serde_json::to_value(fk).unwrap())
        }
        "fk_se3" => {
            let se3 = se3_params_from_input(&inp);
            let fk = forward_kinematics_se3(&se3, &inp.q);
            ("MANIPULATOR_FK_SE3_PASS".into(), serde_json::to_value(fk).unwrap())
        }
        "fk_tree_se3" => {
            let tree = tree_spec_from_input(&inp);
            let target = if inp.target_link.is_empty() {
                "base_link".to_string()
            } else {
                inp.target_link.clone()
            };
            let rep = forward_kinematics_tree(&tree, &inp.q_by_name, &target);
            ("MANIPULATOR_FK_TREE_SE3_PASS".into(), serde_json::to_value(rep).unwrap())
        }
        "ik_tree_se3" => {
            let tree = tree_spec_from_input(&inp);
            let target = if inp.target_link.is_empty() {
                "base_link".to_string()
            } else {
                inp.target_link.clone()
            };
            let ik = inverse_kinematics_tree_position(
                &tree,
                &inp.q_by_name,
                &target,
                inp.target_x,
                inp.target_y,
                inp.target_z,
                80,
                0.05,
                1e-3,
            );
            let pass = ik.converged;
            (
                if pass {
                    "MANIPULATOR_IK_TREE_SE3_PASS".into()
                } else {
                    "MANIPULATOR_IK_TREE_SE3_FAIL".into()
                },
                serde_json::to_value(ik).unwrap(),
            )
        }
        "ik" => {
            let q0 = if inp.q.len() == n {
                inp.q.clone()
            } else {
                default_q(n)
            };
            let ik = inverse_kinematics_dls(&params, inp.target_x, inp.target_y, &q0, 100, 0.05, 1e-5);
            let pass = ik.converged;
            (
                if pass {
                    "MANIPULATOR_IK_PASS".into()
                } else {
                    "MANIPULATOR_IK_FAIL".into()
                },
                serde_json::to_value(ik).unwrap(),
            )
        }
        "jacobian" => {
            let j = jacobian_ee(&params, &inp.q);
            ("MANIPULATOR_JACOBIAN_PASS".into(), serde_json::to_value(j).unwrap())
        }
        "symplectic_step" => {
            let state = SerialArmState {
                q: if inp.q.len() == n {
                    inp.q
                } else {
                    default_q(n)
                },
                q_dot: if inp.q_dot.len() == n {
                    inp.q_dot
                } else {
                    vec![0.1; n]
                },
            };
            let torques = if inp.torques.len() == n {
                inp.torques
            } else {
                vec![0.0; n]
            };
            let rep = symplectic_serial_arm_step(state, &params, &torques, inp.steps, inp.dt);
            let pass = rep.max_rel_drift <= 0.45;
            (
                if pass {
                    "MANIPULATOR_SYMPLECTIC_PASS".into()
                } else {
                    "MANIPULATOR_SYMPLECTIC_FAIL".into()
                },
                serde_json::to_value(rep).unwrap(),
            )
        }
        "fk_ik_roundtrip" => {
            let q = if inp.q.len() == n {
                inp.q
            } else {
                default_q(n)
            };
            let err = fk_ik_roundtrip_error(&params, &q);
            let pass = err <= 0.005;
            (
                if pass {
                    "MANIPULATOR_ROUNDTRIP_PASS".into()
                } else {
                    "MANIPULATOR_ROUNDTRIP_FAIL".into()
                },
                serde_json::json!({ "roundtrip_error_m": err, "q_seed": q }),
            )
        }
        "grasp_force_step" => {
            let rep = grasp_force_step(
                inp.commanded_force_n,
                inp.allowed_max_force_n,
                inp.current_applied_force_n,
                inp.gripper_lever_arm_m,
                inp.ramp_rate_n_per_s,
                inp.dt,
            );
            let pass = rep.applied_force_n <= inp.allowed_max_force_n + 1e-9;
            (
                if pass {
                    "MANIPULATOR_GRASP_FORCE_PASS".into()
                } else {
                    "MANIPULATOR_GRASP_FORCE_FAIL".into()
                },
                serde_json::to_value(rep).unwrap(),
            )
        }
        _ => (
            "MANIPULATOR_OP_UNKNOWN".into(),
            serde_json::json!({ "error": "unknown op", "op": inp.op }),
        ),
    };

    let out = Output {
        verdict: verdict.clone(),
        op: inp.op,
        report,
    };
    println!("{}", serde_json::to_string(&out).expect("serialize"));
}
