# Multi-stage: Rust physics bins + Python Dual socket.
# First build is slow (compiles crates). Runtime: ha-dual-socket in seconds.

FROM rust:1-bookworm AS rust
WORKDIR /src
COPY Cargo.toml Cargo.lock ./
COPY crates ./crates
RUN cargo build -p ha_physics_gate --release \
 && cargo build -p ha_silicon_fuse --release \
 && cargo build -p ha_energy_ledger --release \
 && cargo build -p ha_body_identity --release \
 && cargo build -p universe_kinematic --release --bin manipulator_kinematics_step

FROM python:3.12-slim-bookworm
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgcc-s1 \
 && rm -rf /var/lib/apt/lists/*

COPY --from=rust /src/target/release/ha-physics-gate /app/target/release/ha-physics-gate
COPY --from=rust /src/target/release/ha-silicon-fuse /app/target/release/ha-silicon-fuse
COPY --from=rust /src/target/release/ha-energy-ledger /app/target/release/ha-energy-ledger
COPY --from=rust /src/target/release/ha-body-identity /app/target/release/ha-body-identity
COPY --from=rust /src/target/release/manipulator_kinematics_step /app/target/release/manipulator_kinematics_step

COPY pyproject.toml README.md ./
COPY production_gate ./production_gate
COPY fixtures ./fixtures
COPY results/platform_bpass ./results/platform_bpass
COPY desk ./desk
COPY docs ./docs
COPY START_HERE_PRODUCTION_GATE_V1.md ./

RUN pip install --no-cache-dir -e . \
 && chmod +x /app/target/release/ha-physics-gate \
              /app/target/release/ha-silicon-fuse \
              /app/target/release/ha-energy-ledger \
              /app/target/release/ha-body-identity \
              /app/target/release/manipulator_kinematics_step

ENV PATH="/app/target/release:${PATH}"
ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=utf-8

CMD ["ha-dual-socket", "--preset", "open_diffbot"]
