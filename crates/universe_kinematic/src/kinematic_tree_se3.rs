//! Branched kinematic tree — SE(3) FK per named link (appendage OS crown).

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

use crate::lie_se3_step::Motor7;
use crate::serial_chain_se3::{
    se3_compose_motors, se3_joint_motion_motor, se3_motor_identity, se3_motor_to_fk_report,
    Se3FkReport, Se3JointSpec,
};

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct TreeJointSpec {
    pub name: String,
    pub parent_link: String,
    pub child_link: String,
    pub joint_type: String,
    pub origin_xyz: [f64; 3],
    pub origin_rpy: [f64; 3],
    pub axis_xyz: [f64; 3],
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct KinematicTreeSpec {
    pub root_link: String,
    pub joints: Vec<TreeJointSpec>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct TreeFkReport {
    pub link: String,
    pub pose: Se3FkReport,
    pub links_solved: usize,
}

fn joint_q(joint: &TreeJointSpec, q_by_name: &HashMap<String, f64>) -> f64 {
    match joint.joint_type.as_str() {
        "revolute" | "continuous" | "prismatic" => *q_by_name.get(&joint.name).unwrap_or(&0.0),
        _ => 0.0,
    }
}

fn tree_joint_to_se3(joint: &TreeJointSpec) -> Se3JointSpec {
    Se3JointSpec {
        joint_type: joint.joint_type.clone(),
        origin_xyz: joint.origin_xyz,
        origin_rpy: joint.origin_rpy,
        axis_xyz: joint.axis_xyz,
        link_in_child_frame: false,
    }
}

/// Propagate FK through tree — returns pose of `target_link`.
pub fn forward_kinematics_tree(
    spec: &KinematicTreeSpec,
    q_by_name: &HashMap<String, f64>,
    target_link: &str,
) -> TreeFkReport {
    let mut by_parent: HashMap<String, Vec<&TreeJointSpec>> = HashMap::new();
    for joint in &spec.joints {
        by_parent
            .entry(joint.parent_link.clone())
            .or_default()
            .push(joint);
    }

    let mut link_pose: HashMap<String, Motor7> = HashMap::new();
    link_pose.insert(spec.root_link.clone(), se3_motor_identity());
    let mut queue = vec![spec.root_link.clone()];
    let mut seen: HashMap<String, bool> = HashMap::new();

    while let Some(link) = queue.pop() {
        if *seen.get(&link).unwrap_or(&false) {
            continue;
        }
        seen.insert(link.clone(), true);
        let parent_pose = *link_pose.get(&link).expect("parent link pose");
        if let Some(children) = by_parent.get(&link) {
            for joint in children {
                let q = joint_q(joint, q_by_name);
                let motion = se3_joint_motion_motor(&tree_joint_to_se3(joint), q);
                let child_pose = se3_compose_motors(parent_pose, motion);
                link_pose.insert(joint.child_link.clone(), child_pose);
                queue.push(joint.child_link.clone());
            }
        }
    }

    let pose = link_pose
        .get(target_link)
        .unwrap_or_else(|| panic!("target link not in tree: {target_link}"));
    TreeFkReport {
        link: target_link.to_string(),
        pose: se3_motor_to_fk_report(*pose, "kinematic_tree_se3_fk_v1"),
        links_solved: link_pose.len(),
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct TreeIkReport {
    pub link: String,
    pub q_by_name: HashMap<String, f64>,
    pub ee_x: f64,
    pub ee_y: f64,
    pub ee_z: f64,
    pub iterations: usize,
    pub final_error_m: f64,
    pub converged: bool,
    pub backend_id: String,
}

fn path_joints_to_link<'a>(
    spec: &'a KinematicTreeSpec,
    target_link: &str,
) -> Vec<&'a TreeJointSpec> {
    let mut parent_joint: HashMap<String, &'a TreeJointSpec> = HashMap::new();
    for joint in &spec.joints {
        parent_joint.insert(joint.child_link.clone(), joint);
    }
    let mut path: Vec<&TreeJointSpec> = Vec::new();
    let mut link = target_link.to_string();
    while link != spec.root_link {
        let joint = parent_joint
            .get(&link)
            .unwrap_or_else(|| panic!("no parent joint for link {link}"));
        path.push(*joint);
        link = joint.parent_link.clone();
    }
    path.reverse();
    path
}

fn is_active_joint(jtype: &str) -> bool {
    matches!(jtype, "revolute" | "continuous" | "prismatic")
}

/// Numeric position IK on joints along path root → target_link.
pub fn inverse_kinematics_tree_position(
    spec: &KinematicTreeSpec,
    q0: &HashMap<String, f64>,
    target_link: &str,
    target_x: f64,
    target_y: f64,
    target_z: f64,
    max_iter: usize,
    lambda: f64,
    tol_m: f64,
) -> TreeIkReport {
    let path = path_joints_to_link(spec, target_link);
    let active: Vec<&TreeJointSpec> = path
        .iter()
        .copied()
        .filter(|j| is_active_joint(&j.joint_type))
        .collect();
    let mut q_map = q0.clone();
    for j in &active {
        q_map.entry(j.name.clone()).or_insert(0.0);
    }

    let mut err = f64::INFINITY;
    let mut iters = 0usize;
    for k in 0..max_iter {
        iters = k + 1;
        let fk = forward_kinematics_tree(spec, &q_map, target_link);
        let ex = target_x - fk.pose.ee_x;
        let ey = target_y - fk.pose.ee_y;
        let ez = target_z - fk.pose.ee_z;
        err = (ex * ex + ey * ey + ez * ez).sqrt();
        if err <= tol_m {
            break;
        }
        let n = active.len();
        if n == 0 {
            break;
        }
        let eps = 1e-6;
        let mut j_flat = vec![0.0_f64; 3 * n];
        for (col, joint) in active.iter().enumerate() {
            let saved = *q_map.get(&joint.name).unwrap();
            let mut qp = q_map.clone();
            qp.insert(joint.name.clone(), saved + eps);
            let fp = forward_kinematics_tree(spec, &qp, target_link);
            j_flat[col] = (fp.pose.ee_x - fk.pose.ee_x) / eps;
            j_flat[n + col] = (fp.pose.ee_y - fk.pose.ee_y) / eps;
            j_flat[2 * n + col] = (fp.pose.ee_z - fk.pose.ee_z) / eps;
        }
        let mut a00 = lambda * lambda;
        let mut a01 = 0.0;
        let mut a02 = 0.0;
        let mut a11 = lambda * lambda;
        let mut a12 = 0.0;
        let mut a22 = lambda * lambda;
        for col in 0..n {
            let j0 = j_flat[col];
            let j1 = j_flat[n + col];
            let j2 = j_flat[2 * n + col];
            a00 += j0 * j0;
            a01 += j0 * j1;
            a02 += j0 * j2;
            a11 += j1 * j1;
            a12 += j1 * j2;
            a22 += j2 * j2;
        }
        let det = a00 * (a11 * a22 - a12 * a12) - a01 * (a01 * a22 - a02 * a12) + a02 * (a01 * a12 - a02 * a11);
        if det.abs() < 1e-12 {
            break;
        }
        let inv00 = (a11 * a22 - a12 * a12) / det;
        let inv01 = (a02 * a12 - a01 * a22) / det;
        let inv02 = (a01 * a12 - a02 * a11) / det;
        let inv11 = (a00 * a22 - a02 * a02) / det;
        let inv12 = (a02 * a01 - a00 * a12) / det;
        let inv22 = (a00 * a11 - a01 * a01) / det;
        let v0 = inv00 * ex + inv01 * ey + inv02 * ez;
        let v1 = inv01 * ex + inv11 * ey + inv12 * ez;
        let v2 = inv02 * ex + inv12 * ey + inv22 * ez;
        for (col, joint) in active.iter().enumerate() {
            let dq = j_flat[col] * v0 + j_flat[n + col] * v1 + j_flat[2 * n + col] * v2;
            let entry = q_map.get_mut(&joint.name).unwrap();
            *entry += dq;
        }
    }
    let fk = forward_kinematics_tree(spec, &q_map, target_link);
    TreeIkReport {
        link: target_link.to_string(),
        q_by_name: q_map,
        ee_x: fk.pose.ee_x,
        ee_y: fk.pose.ee_y,
        ee_z: fk.pose.ee_z,
        iterations: iters,
        final_error_m: err,
        converged: err <= tol_m,
        backend_id: "kinematic_tree_se3_ik_v1".into(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn carrier_tree() -> KinematicTreeSpec {
        KinematicTreeSpec {
            root_link: "base_link".into(),
            joints: vec![
                TreeJointSpec {
                    name: "wheel_fl_joint".into(),
                    parent_link: "base_link".into(),
                    child_link: "wheel_fl_link".into(),
                    joint_type: "continuous".into(),
                    origin_xyz: [-0.25, -0.165, 0.10],
                    origin_rpy: [1.5708, 0.0, 0.0],
                    axis_xyz: [0.0, 0.0, 1.0],
                },
                TreeJointSpec {
                    name: "wheel_fr_joint".into(),
                    parent_link: "base_link".into(),
                    child_link: "wheel_fr_link".into(),
                    joint_type: "continuous".into(),
                    origin_xyz: [0.25, -0.165, 0.10],
                    origin_rpy: [1.5708, 0.0, 0.0],
                    axis_xyz: [0.0, 0.0, 1.0],
                },
            ],
        }
    }

    #[test]
    fn branched_wheels_separate() {
        let spec = carrier_tree();
        let mut q = HashMap::new();
        q.insert("wheel_fl_joint".to_string(), 0.0);
        q.insert("wheel_fr_joint".to_string(), 0.0);
        let fl = forward_kinematics_tree(&spec, &q, "wheel_fl_link");
        let fr = forward_kinematics_tree(&spec, &q, "wheel_fr_link");
        assert!((fl.pose.ee_x - (-0.25)).abs() < 1e-3);
        assert!((fr.pose.ee_x - 0.25).abs() < 1e-3);
        assert!(fl.links_solved >= 3);
    }
}
