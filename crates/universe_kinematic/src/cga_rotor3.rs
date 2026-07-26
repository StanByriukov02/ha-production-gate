//! Cl(3,0) rotor — 3D rigid rotation (CGA-class geometric backend).
//! Conformal Cl(4,1) for full robot+translation is a later promote; rotors are the same algebra slice.

#[derive(Clone, Copy, Debug)]
pub struct Rotor3 {
    pub s: f64,
    pub b12: f64,
    pub b23: f64,
    pub b31: f64,
}

#[derive(Clone, Copy, Debug)]
pub struct Vec3 {
    pub x: f64,
    pub y: f64,
    pub z: f64,
}

impl Rotor3 {
    pub fn identity() -> Self {
        Self {
            s: 1.0,
            b12: 0.0,
            b23: 0.0,
            b31: 0.0,
        }
    }

    pub fn from_axis_angle(axis: Vec3, angle: f64) -> Self {
        let n = axis.norm().max(1e-12);
        let half = 0.5 * angle;
        let c = half.cos();
        let s = half.sin();
        Self {
            s: c,
            b12: s * axis.x / n,
            b23: s * axis.y / n,
            b31: s * axis.z / n,
        }
    }

    pub fn reverse(self) -> Self {
        Self {
            s: self.s,
            b12: -self.b12,
            b23: -self.b23,
            b31: -self.b31,
        }
    }

    pub fn norm(self) -> f64 {
        (self.s * self.s + self.b12 * self.b12 + self.b23 * self.b23 + self.b31 * self.b31).sqrt()
    }

    pub fn normalize(self) -> Self {
        let n = self.norm().max(1e-15);
        Self {
            s: self.s / n,
            b12: self.b12 / n,
            b23: self.b23 / n,
            b31: self.b31 / n,
        }
    }

    pub fn mul(self, other: Self) -> Self {
        // Geometric product for rotors in Cl(3,0)
        Self {
            s: self.s * other.s - self.b12 * other.b12 - self.b23 * other.b23 - self.b31 * other.b31,
            b12: self.s * other.b12 + self.b12 * other.s + self.b23 * other.b31 - self.b31 * other.b23,
            b23: self.s * other.b23 - self.b12 * other.b31 + self.b23 * other.s + self.b31 * other.b12,
            b31: self.s * other.b31 + self.b12 * other.b23 - self.b23 * other.b12 + self.b31 * other.s,
        }
    }

    pub fn rotate(self, v: Vec3) -> Vec3 {
        // v' = R v R~  (treat v as pure vector: s=0)
        let rv = Rotor3 {
            s: 0.0,
            b12: v.x,
            b23: v.y,
            b31: v.z,
        };
        let out = self.mul(rv).mul(self.reverse());
        Vec3 {
            x: out.b12,
            y: out.b23,
            z: out.b31,
        }
    }
}

impl Vec3 {
    pub fn new(x: f64, y: f64, z: f64) -> Self {
        Self { x, y, z }
    }

    pub fn norm(self) -> f64 {
        (self.x * self.x + self.y * self.y + self.z * self.z).sqrt()
    }

    pub fn dot(self, o: Self) -> f64 {
        self.x * o.x + self.y * o.y + self.z * o.z
    }

    pub fn cross(self, o: Self) -> Self {
        Self {
            x: self.y * o.z - self.z * o.y,
            y: self.z * o.x - self.x * o.z,
            z: self.x * o.y - self.y * o.x,
        }
    }

    pub fn scale(self, k: f64) -> Self {
        Self {
            x: self.x * k,
            y: self.y * k,
            z: self.z * k,
        }
    }

    pub fn add(self, o: Self) -> Self {
        Self {
            x: self.x + o.x,
            y: self.y + o.y,
            z: self.z + o.z,
        }
    }
}

/// Rigid link state: rotor orientation + angular velocity bivector components.
#[derive(Clone, Copy, Debug)]
pub struct CgaPendulumState {
    pub r: Rotor3,
    pub omega: Vec3,
    pub com: Vec3,
}

pub struct CgaPendulumParams {
    pub mass: f64,
    pub length: f64,
    pub gravity: f64,
    pub inertia: f64,
}

impl CgaPendulumParams {
    pub fn robot_link_default() -> Self {
        Self {
            mass: 1.0,
            length: 0.5,
            gravity: 9.81,
            inertia: 0.25,
        }
    }
}

pub fn cga_energy(state: &CgaPendulumState, p: &CgaPendulumParams) -> f64 {
    let rotated = state.r.rotate(Vec3::new(0.0, 0.0, -p.length));
    let height = rotated.z;
    let omega_sq = state.omega.dot(state.omega);
    0.5 * p.inertia * omega_sq + p.mass * p.gravity * height
}

/// Integrate one step: dR/dt = 0.5 * B * R with torque from gravity on COM.
pub fn cga_step(state: &mut CgaPendulumState, p: &CgaPendulumParams, dt: f64) {
    let r_com = state.r.rotate(Vec3::new(0.0, 0.0, -p.length));
    let force = Vec3::new(0.0, 0.0, -p.mass * p.gravity);
    let torque = r_com.cross(force);
    let alpha = torque.scale(1.0 / p.inertia);

    // Symplectic-ish split on rotor manifold
    state.omega = state.omega.add(alpha.scale(dt));
    let omega_mag = state.omega.norm();
    if omega_mag > 1e-12 {
        let axis = state.omega.scale(1.0 / omega_mag);
        let delta = Rotor3::from_axis_angle(axis, omega_mag * dt);
        state.r = delta.mul(state.r).normalize();
    }
}

pub fn mlcc_jerk_proxy(prev_omega: Vec3, omega: Vec3, dt: f64) -> f64 {
    let d = omega.add(prev_omega.scale(-1.0));
    d.norm() / dt.max(1e-12)
}
