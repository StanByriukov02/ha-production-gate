"""Drive Clifford ALU through MMIO RTL sim — iron-in-loop glue (not GP engine)."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
_FIX = _REPO / "fixtures" / "chip"
_GEN_LC2 = _REPO / "scripts" / "chip" / "gen_clifford_lc2_pose_rtl_tb_v0_sv.py"
_GEN_WORLD = _REPO / "scripts" / "chip" / "gen_clifford_world_motion_iron_v0.py"
_MAPPED_NETLIST = _REPO / "results" / "platform_bpass" / "chip" / "sta" / "clifford_sta_geo_prod_slice_mapped_v0.v"
_MAPPED_ALU_NETLIST = _REPO / "results" / "platform_bpass" / "chip" / "sta" / "clifford_sta_alu_slice_mapped_v0.v"
_MAPPED_HYBRID_NETLIST = _REPO / "results" / "platform_bpass" / "chip" / "sta" / "clifford_sta_geo_prod_slice_mapped_hybrid_v0.v"
_MAPPED_ALU_HYBRID_NETLIST = _REPO / "results" / "platform_bpass" / "chip" / "sta" / "clifford_sta_alu_slice_mapped_hybrid_v0.v"
_NANGATE_PRIM = _FIX / "sta" / "nangate45_sim_primitives_v0.v"
_MAPPED_ARITH_RTL = (
    "clifford_f32_synth_v0.v",
    "clifford_geo_prod_synth_low_lo_blades_v0.v",
    "clifford_geo_prod_synth_low_hi_blades_v0.v",
    "clifford_geo_prod_synth_high_lo_blades_v0.v",
    "clifford_geo_prod_synth_high_hi_blades_v0.v",
)
_MAPPED_ALU_ARITH_RTL = (
    "clifford_f32_synth_v0.v",
    "clifford_f32_nr_v0.v",
    "clifford_geo_prod_synth_v0.v",
    "clifford_geo_prod_synth_low_blades_v0.v",
    "clifford_geo_prod_synth_low_lo_blades_v0.v",
    "clifford_geo_prod_synth_low_hi_blades_v0.v",
    "clifford_geo_prod_synth_high_blades_v0.v",
    "clifford_geo_prod_synth_high_lo_blades_v0.v",
    "clifford_geo_prod_synth_high_hi_blades_v0.v",
    "clifford_reverse_synth_v0.v",
    "clifford_norm_synth_acc7_v0.v",
    "clifford_norm_synth_scale_v0.v",
    "clifford_norm_synth_v0.v",
    "clifford_norm_synth_acc_low_v0.v",
    "clifford_norm_synth_acc_tail_v0.v",
    "clifford_norm_synth_tail_v0.v",
    "clifford_geo_prod_cga_synth_v0.v",
)
_MAPPED_STRIP_MODULES = frozenset(
    {
        "bf16_mul_widen_f32_v0",
        "clifford_geo_prod_synth_high_hi_blades_v0",
        "clifford_geo_prod_synth_high_lo_blades_v0",
        "clifford_geo_prod_synth_low_hi_blades_v0",
        "clifford_geo_prod_synth_low_lo_blades_v0",
        "f32_add_synth_v0",
        "f32_mul_synth_v0",
        "f32_to_bf16_rne_v0",
    }
)
_MAPPED_ALU_STRIP_MODULES = _MAPPED_STRIP_MODULES | frozenset(
    {
        "clifford_geo_prod_synth_high_blades_v0",
        "clifford_geo_prod_synth_low_blades_v0",
        "clifford_geo_prod_cga_synth_v0",
        "clifford_norm_synth_acc7_v0",
        "clifford_norm_synth_acc_low_v0",
        "clifford_norm_synth_acc_tail_v0",
        "clifford_norm_synth_scale_v0",
        "clifford_norm_synth_tail_v0",
        "clifford_norm_synth_v0",
        "clifford_reverse_synth_v0",
        "f32_rcp_one_nr_v0",
        "f32_rcp_seed_v0",
        "f32_sqrt_one_iter_v0",
        "f32_sqrt_seed_v0",
    }
)


def _mmio_iron_rtl_closure(*tb_modules: str) -> tuple[str, ...]:
    """Full ALU RTL closure (P6 MMIO iron-in-loop) — same file set as alu_tb_hygiene minus unit TB."""
    if str(_REPO) not in __import__("sys").path:
        __import__("sys").path.insert(0, str(_REPO))
    from scripts.chip.clifford_alu_tb_hygiene_v1 import _ALU_RTL

    base = tuple(s for s in _ALU_RTL if s != "clifford_alu_tb_v0.v")
    return base + ("clifford_alu_mmio_v0.v",) + tb_modules


_RTL_LC2_SRCS = _mmio_iron_rtl_closure("clifford_lc2_pose_rtl_tb_v0.v")
_RTL_WORLD_SRCS = _mmio_iron_rtl_closure("clifford_world_motion_rtl_tb_v0.v")
_MSYS_ROOT = Path(r"C:\msys64")
_MSYS_MINGW = _MSYS_ROOT / "mingw64" / "bin"
_MSYS_SHELL = _MSYS_ROOT / "msys2_shell.cmd"


def _mingw_env() -> dict[str, str]:
    env = os.environ.copy()
    prefix = f"{_MSYS_MINGW};{_MSYS_ROOT / 'usr' / 'bin'}"
    env["PATH"] = f"{prefix};{env.get('PATH', '')}"
    return env


def _posix_path(path: Path) -> str:
    s = str(path.resolve())
    if len(s) >= 2 and s[1] == ":":
        return "/" + s[0].lower() + s[2:].replace("\\", "/")
    return s.replace("\\", "/")


def _run_mingw_shell(command: str, *, timeout: int = 600) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(_MSYS_SHELL), "-mingw64", "-defterm", "-no-start", "-c", command],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _skip_tb_regen() -> bool:
    return os.environ.get("CLIFFORD_SKIP_TB_REGEN", "").strip() in ("1", "true", "yes")


def _regenerate_lc2_tb() -> None:
    if _skip_tb_regen():
        return
    subprocess.run(
        [__import__("sys").executable, str(_GEN_LC2)],
        check=True,
        cwd=str(_REPO),
    )


def _regenerate_world_tb() -> None:
    if _skip_tb_regen():
        return
    subprocess.run(
        [__import__("sys").executable, str(_GEN_WORLD)],
        check=True,
        cwd=str(_REPO),
    )


def _regenerate_structural_tbs() -> None:
    if _skip_tb_regen():
        return
    if str(_REPO) not in __import__("sys").path:
        __import__("sys").path.insert(0, str(_REPO))
    from scripts.chip.gen_clifford_world_motion_iron_v0 import (
        mint_world_motion_vectors,
        write_world_motion_mapped_mmio_rtl_tb,
        write_world_motion_mapped_slice_rtl_tb,
        write_world_motion_structural_rtl_tb,
    )

    vectors = mint_world_motion_vectors()
    write_world_motion_structural_rtl_tb(vectors)
    write_world_motion_mapped_slice_rtl_tb(vectors)
    tick_cap = int(__import__("os").environ.get("CLIFFORD_MAPPED_TICKS", "50"))
    write_world_motion_mapped_mmio_rtl_tb(vectors, n_ticks=tick_cap)


def _parse_rtl_pose(stdout: str) -> list[tuple[float, float, float]]:
    pts: list[tuple[float, float, float]] = []
    for line in stdout.splitlines():
        m = re.match(r"RTL_POSE\s+(\d+)\s+([-+eE0-9.]+)\s+([-+eE0-9.]+)\s+([-+eE0-9.]+)", line.strip())
        if m:
            pts.append((float(m.group(2)), float(m.group(3)), float(m.group(4))))
    return pts


def _parse_rtl_mapped_pose(stdout: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in stdout.splitlines():
        m = re.match(
            r"RTL_MAPPED_POSE\s+(\d+)\s+([-+eE0-9.]+)\s+([-+eE0-9.]+)\s+([-+eE0-9.]+)\s+([-+eE0-9.]+)",
            line.strip(),
        )
        if m:
            rows.append(
                {
                    "tick": int(m.group(1)),
                    "meters": float(m.group(2)),
                    "x_m": float(m.group(3)),
                    "y_m": float(m.group(4)),
                    "z_m": float(m.group(5)),
                }
            )
    return rows


def _parse_rtl_world_pose(stdout: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in stdout.splitlines():
        m = re.match(
            r"RTL_WORLD_POSE\s+(\d+)\s+([-+eE0-9.]+)\s+([-+eE0-9.]+)\s+([-+eE0-9.]+)\s+([-+eE0-9.]+)",
            line.strip(),
        )
        if m:
            rows.append(
                {
                    "tick": int(m.group(1)),
                    "meters": float(m.group(2)),
                    "x_m": float(m.group(3)),
                    "y_m": float(m.group(4)),
                    "z_m": float(m.group(5)),
                }
            )
    return rows


def _run_rtl_tb(
    *,
    rtl_srcs: tuple[str, ...],
    top_module: str,
    pass_token: str,
    tmp_prefix: str,
    backend: str = "auto",
    iverilog_defines: tuple[str, ...] = (),
) -> dict[str, Any]:
    out = ""
    status = "FAIL"
    used = backend

    if backend in ("auto", "iverilog"):
        iverilog = shutil.which("iverilog") or shutil.which("iverilog.exe")
        vvp = shutil.which("vvp") or shutil.which("vvp.exe")
        if not iverilog and (_MSYS_MINGW / "iverilog.exe").is_file():
            iverilog = str(_MSYS_MINGW / "iverilog.exe")
        if not vvp and (_MSYS_MINGW / "vvp.exe").is_file():
            vvp = str(_MSYS_MINGW / "vvp.exe")
        if iverilog and vvp:
            with tempfile.TemporaryDirectory(prefix=tmp_prefix) as tmp:
                out_vvp = Path(tmp) / "sim.vvp"
                iv = subprocess.run(
                    [iverilog, "-g2012", *iverilog_defines, "-o", str(out_vvp), "-I", str(_FIX), *[_FIX / s for s in rtl_srcs]],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=300,
                    env=_mingw_env(),
                )
                if iv.returncode == 0 and out_vvp.is_file():
                    sim = subprocess.run(
                        [vvp, str(out_vvp)],
                        capture_output=True,
                        text=True,
                        timeout=300,
                        env=_mingw_env(),
                    )
                    out = (sim.stdout or "") + (sim.stderr or "")
                    if sim.returncode == 0 and pass_token in out:
                        status = "PASS"
                        used = "iverilog"
                else:
                    out = (iv.stderr or "") + (iv.stdout or "")

    if status != "PASS" and backend in ("auto", "verilator") and _MSYS_SHELL.is_file():
        fix_posix = _posix_path(_FIX)
        with tempfile.TemporaryDirectory(prefix=tmp_prefix) as tmp:
            build_posix = _posix_path(Path(tmp) / "build")
            srcs = " ".join(rtl_srcs)
            exe = f"V{top_module}.exe"
            cmd = (
                f"cd '{fix_posix}' && mkdir -p '{build_posix}' && "
                f"verilator --binary --top-module {top_module} -Wall -Wno-fatal "
                f"-CFLAGS '-D_GLIBCXX_USE_CXX11_ABI=0' -LDFLAGS '-lstdc++' -I. "
                f"-Mdir '{build_posix}' {srcs} && "
                f"'{build_posix}/{exe}'"
            )
            proc = _run_mingw_shell(cmd, timeout=900)
            out = (proc.stdout or "") + (proc.stderr or "")
            if proc.returncode == 0 and pass_token in out:
                status = "PASS"
                used = "verilator"

    return {"backend": used, "status": status, "stdout": out, "stdout_tail": out[-1500:]}


def _run_synth_slice_rtl_tb(*, backend: str = "auto") -> dict[str, Any]:
    """T2.22a — RTL synth geo_prod slice with full pipeline stimulus (pre-mapped)."""
    _regenerate_structural_tbs()
    tb = _FIX / "sta" / "clifford_world_motion_mapped_slice_rtl_tb_v0.v"
    synth_srcs = [
        "sta/clifford_sta_sim_blackbox_v0.v",
        "clifford_f32_synth_v0.v",
        "clifford_geo_prod_synth_v0.v",
        "clifford_geo_prod_synth_low_blades_v0.v",
        "clifford_geo_prod_synth_low_lo_blades_v0.v",
        "clifford_geo_prod_synth_low_hi_blades_v0.v",
        "clifford_geo_prod_synth_high_blades_v0.v",
        "clifford_geo_prod_synth_high_lo_blades_v0.v",
        "clifford_geo_prod_synth_high_hi_blades_v0.v",
        "clifford_geo_prod_ex_pipe_v0.v",
        "sta/clifford_sta_geo_prod_slice_top_v0.v",
        "sta/clifford_world_motion_mapped_slice_rtl_tb_v0.v",
    ]
    sim = _run_rtl_tb(
        rtl_srcs=tuple(synth_srcs),
        top_module="clifford_world_motion_mapped_slice_rtl_tb_v0",
        pass_token="TB_PASS rtl_world_motion_mapped_slice",
        tmp_prefix="clifford_synth_slice_",
        backend=backend,
        iverilog_defines=("-DCLIFFORD_GP_DATAPATH_SYNTH_ONLY",),
    )
    return sim


def _strip_verilog_modules(src: str, drop: frozenset[str]) -> str:
    """Drop whole module definitions (yosys netlist is flat)."""
    out: list[str] = []
    skip = False
    for line in src.splitlines(keepends=True):
        m = re.match(r"^\s*module\s+(\w+)\b", line)
        if m and not skip:
            if m.group(1) in drop:
                skip = True
                continue
        if skip:
            if re.match(r"^\s*endmodule\b", line):
                skip = False
            continue
        out.append(line)
    return "".join(out)


def _write_mapped_alu_hybrid_netlist() -> Path:
    """Full ALU gate pipeline/control netlist + RTL arithmetic (H1 hybrid funcsim)."""
    src = _MAPPED_ALU_NETLIST.read_text(encoding="utf-8")
    hybrid = _strip_verilog_modules(src, _MAPPED_ALU_STRIP_MODULES)
    header = (
        "// AUTO hybrid funcsim — Nangate45 ALU ex_pipe + RTL f32/blades/norm\n"
        f"// Source: {_MAPPED_ALU_NETLIST.relative_to(_REPO).as_posix()}\n"
    )
    _MAPPED_ALU_HYBRID_NETLIST.parent.mkdir(parents=True, exist_ok=True)
    _MAPPED_ALU_HYBRID_NETLIST.write_text(header + hybrid, encoding="utf-8")
    return _MAPPED_ALU_HYBRID_NETLIST


def _mapped_alu_hybrid_netlist_path() -> Path:
    if not _MAPPED_ALU_HYBRID_NETLIST.is_file() or (
        _MAPPED_ALU_NETLIST.is_file()
        and _MAPPED_ALU_NETLIST.stat().st_mtime > _MAPPED_ALU_HYBRID_NETLIST.stat().st_mtime
    ):
        return _write_mapped_alu_hybrid_netlist()
    return _MAPPED_ALU_HYBRID_NETLIST


def _write_mapped_hybrid_netlist() -> Path:
    """Gate pipeline/control netlist + RTL arithmetic (iverilog cannot sim mapped comb mul)."""
    src = _MAPPED_NETLIST.read_text(encoding="utf-8")
    hybrid = _strip_verilog_modules(src, _MAPPED_STRIP_MODULES)
    header = (
        "// AUTO hybrid funcsim — Nangate45 ex_pipe pipeline + RTL f32/blades\n"
        f"// Source: {_MAPPED_NETLIST.relative_to(_REPO).as_posix()}\n"
    )
    _MAPPED_HYBRID_NETLIST.parent.mkdir(parents=True, exist_ok=True)
    _MAPPED_HYBRID_NETLIST.write_text(header + hybrid, encoding="utf-8")
    return _MAPPED_HYBRID_NETLIST


def _mapped_hybrid_netlist_path() -> Path:
    if not _MAPPED_HYBRID_NETLIST.is_file() or (
        _MAPPED_NETLIST.is_file()
        and _MAPPED_NETLIST.stat().st_mtime > _MAPPED_HYBRID_NETLIST.stat().st_mtime
    ):
        return _write_mapped_hybrid_netlist()
    return _MAPPED_HYBRID_NETLIST


def _run_mapped_slice_tb(*, backend: str = "auto") -> dict[str, Any]:
    import os

    _regenerate_structural_tbs()
    if not _MAPPED_NETLIST.is_file() or not _NANGATE_PRIM.is_file():
        return {"backend": backend, "status": "FAIL", "stdout": "mapped_netlist_or_primitives_missing", "stdout_tail": ""}
    _mapped_hybrid_netlist_path()  # keep hybrid artifact fresh for fallback
    use_hybrid = os.environ.get("CLIFFORD_MAPPED_HYBRID", "").strip() in ("1", "true", "yes")
    netlist_path = _MAPPED_HYBRID_NETLIST if use_hybrid else _MAPPED_NETLIST
    netlist_posix = _posix_path(netlist_path)
    tick_cap = int(os.environ.get("CLIFFORD_MAPPED_TICKS", "50"))
    tb = _FIX / "sta" / "clifford_world_motion_mapped_slice_rtl_tb_v0.v"
    repo_posix = _posix_path(_REPO)
    prim_posix = _posix_path(_NANGATE_PRIM)
    tb_posix = _posix_path(tb)
    fix_posix = _posix_path(_FIX)
    arith_posix = " ".join(f"'{_posix_path(_FIX / s)}'" for s in _MAPPED_ARITH_RTL)
    out = ""
    status = "FAIL"
    used = backend
    if backend in ("auto", "iverilog") and _MSYS_SHELL.is_file():
        with tempfile.TemporaryDirectory(prefix="clifford_mapped_slice_") as tmp:
            out_vvp = _posix_path(Path(tmp) / "sim.vvp")
            arith_srcs = f" {arith_posix}" if use_hybrid else ""
            cmd = (
                f"cd '{repo_posix}' && iverilog -g2012 -o '{out_vvp}' -I '{fix_posix}' "
                f"'{prim_posix}' '{netlist_posix}'{arith_srcs} '{tb_posix}' && vvp '{out_vvp}'"
            )
            proc = _run_mingw_shell(cmd, timeout=1200)
            out = (proc.stdout or "") + (proc.stderr or "")
            if proc.returncode == 0 and "TB_PASS rtl_world_motion_mapped_slice" in out:
                status = "PASS"
                used = "iverilog_mapped_hybrid" if use_hybrid else "iverilog_mapped"
    return {
        "backend": used,
        "status": status,
        "stdout": out,
        "stdout_tail": out[-2000:],
        "tick_cap": tick_cap,
        "sim_layer": "mapped_netlist_slice" if used == "iverilog_mapped" else "mapped_hybrid_gate_pipe_rtl_arith",
    }


def _run_mapped_alu_mmio_tb(*, backend: str = "auto") -> dict[str, Any]:
    import os

    _regenerate_structural_tbs()
    if not _MAPPED_ALU_NETLIST.is_file() or not _NANGATE_PRIM.is_file():
        return {"backend": backend, "status": "FAIL", "stdout": "mapped_alu_netlist_or_primitives_missing", "stdout_tail": ""}
    _mapped_alu_hybrid_netlist_path()
    use_hybrid = os.environ.get("CLIFFORD_MAPPED_ALU_HYBRID", os.environ.get("CLIFFORD_MAPPED_HYBRID", "")).strip() in (
        "1",
        "true",
        "yes",
    )
    netlist_path = _MAPPED_ALU_HYBRID_NETLIST if use_hybrid else _MAPPED_ALU_NETLIST
    tick_cap = int(os.environ.get("CLIFFORD_MAPPED_TICKS", "50"))
    tb = _FIX / "sta" / "clifford_world_motion_mapped_mmio_rtl_tb_v0.v"
    mmio = _FIX / "clifford_alu_mmio_v0.v"
    repo_posix = _posix_path(_REPO)
    netlist_posix = _posix_path(netlist_path)
    prim_posix = _posix_path(_NANGATE_PRIM)
    tb_posix = _posix_path(tb)
    mmio_posix = _posix_path(mmio)
    fix_posix = _posix_path(_FIX)
    arith_posix = " ".join(f"'{_posix_path(_FIX / s)}'" for s in _MAPPED_ALU_ARITH_RTL)
    out = ""
    status = "FAIL"
    used = backend
    pass_token = "TB_PASS rtl_world_motion_mapped_mmio"

    def _mapped_srcs() -> list[Path]:
        srcs: list[Path] = [_NANGATE_PRIM, netlist_path]
        if use_hybrid:
            srcs.extend(_FIX / s for s in _MAPPED_ALU_ARITH_RTL)
        srcs.extend([mmio, tb])
        return srcs

    if backend in ("auto", "iverilog"):
        iverilog = shutil.which("iverilog") or shutil.which("iverilog.exe")
        vvp = shutil.which("vvp") or shutil.which("vvp.exe")
        if not iverilog and (_MSYS_MINGW / "iverilog.exe").is_file():
            iverilog = str(_MSYS_MINGW / "iverilog.exe")
        if not vvp and (_MSYS_MINGW / "vvp.exe").is_file():
            vvp = str(_MSYS_MINGW / "vvp.exe")
        if iverilog and vvp:
            with tempfile.TemporaryDirectory(prefix="clifford_mapped_alu_mmio_") as tmp:
                out_vvp = Path(tmp) / "sim.vvp"
                iv = subprocess.run(
                    [iverilog, "-g2012", "-o", str(out_vvp), "-I", str(_FIX), *[str(p) for p in _mapped_srcs()]],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=2400,
                    env=_mingw_env(),
                )
                if iv.returncode == 0 and out_vvp.is_file():
                    sim = subprocess.run(
                        [vvp, str(out_vvp)],
                        capture_output=True,
                        text=True,
                        timeout=2400,
                        env=_mingw_env(),
                    )
                    out = (sim.stdout or "") + (sim.stderr or "")
                    if sim.returncode == 0 and pass_token in out:
                        status = "PASS"
                        used = "iverilog_mapped_alu_hybrid" if use_hybrid else "iverilog_mapped_alu_mmio"
                else:
                    out = (iv.stderr or "") + (iv.stdout or "")

    if status != "PASS" and backend in ("auto", "iverilog") and _MSYS_SHELL.is_file():
        with tempfile.TemporaryDirectory(prefix="clifford_mapped_alu_mmio_") as tmp:
            out_vvp = _posix_path(Path(tmp) / "sim.vvp")
            arith_srcs = f" {arith_posix}" if use_hybrid else ""
            cmd = (
                f"cd '{repo_posix}' && iverilog -g2012 -o '{out_vvp}' -I '{fix_posix}' "
                f"'{prim_posix}' '{netlist_posix}'{arith_srcs} '{mmio_posix}' '{tb_posix}' && vvp '{out_vvp}'"
            )
            proc = _run_mingw_shell(cmd, timeout=2400)
            out = (proc.stdout or "") + (proc.stderr or "")
            if proc.returncode == 0 and pass_token in out:
                status = "PASS"
                used = "iverilog_mapped_alu_hybrid" if use_hybrid else "iverilog_mapped_alu_mmio"
    return {
        "backend": used,
        "status": status,
        "stdout": out,
        "stdout_tail": out[-2000:],
        "tick_cap": tick_cap,
        "sim_layer": "mapped_hybrid_full_alu_mmio" if use_hybrid else "mapped_full_alu_mmio",
    }


def run_iron_lc2_pose_sim(*, backend: str = "auto") -> dict[str, Any]:
    """Run RTL LC2 pose TB; return parsed points + backend status."""
    _regenerate_lc2_tb()
    sim = _run_rtl_tb(
        rtl_srcs=_RTL_LC2_SRCS,
        top_module="clifford_lc2_pose_rtl_tb_v0",
        pass_token="TB_PASS rtl_lc2_pose",
        tmp_prefix="clifford_lc2_iron_",
        backend=backend,
    )
    points = _parse_rtl_pose(sim["stdout"])
    return {
        "backend": sim["backend"],
        "status": sim["status"],
        "point_count": len(points),
        "points": points,
        "stdout_tail": sim["stdout_tail"],
    }


def run_iron_world_motion_sim(*, backend: str = "auto") -> dict[str, Any]:
    """Run RTL world combat TB — 2× GEO_PROD MMIO per traverse tick (behavioral sim path)."""
    _regenerate_world_tb()
    sim = _run_rtl_tb(
        rtl_srcs=_RTL_WORLD_SRCS,
        top_module="clifford_world_motion_rtl_tb_v0",
        pass_token="TB_PASS rtl_world_motion",
        tmp_prefix="clifford_world_iron_",
        backend=backend,
    )
    ticks = _parse_rtl_world_pose(sim["stdout"])
    return {
        "backend": sim["backend"],
        "status": sim["status"],
        "tick_count": len(ticks),
        "ticks": ticks,
        "stdout_tail": sim["stdout_tail"],
        "sim_layer": "behavioral_mmio",
    }


def run_iron_world_motion_structural_sim(*, backend: str = "auto") -> dict[str, Any]:
    """MMIO + gp_synth_en=1 — synthesizable structural datapath (pre-map)."""
    _regenerate_structural_tbs()
    struct_srcs = tuple(
        "clifford_world_motion_structural_rtl_tb_v0.v" if s == "clifford_world_motion_rtl_tb_v0.v" else s
        for s in _RTL_WORLD_SRCS
    )
    sim = _run_rtl_tb(
        rtl_srcs=struct_srcs,
        top_module="clifford_world_motion_structural_rtl_tb_v0",
        pass_token="TB_PASS rtl_world_motion_structural",
        tmp_prefix="clifford_world_struct_",
        backend=backend,
    )
    ticks = _parse_rtl_world_pose(sim["stdout"])
    return {
        "backend": sim["backend"],
        "status": sim["status"],
        "tick_count": len(ticks),
        "ticks": ticks,
        "stdout_tail": sim["stdout_tail"],
        "sim_layer": "structural_synth_mmio",
    }


def run_iron_world_motion_synth_slice_sim(*, backend: str = "auto") -> dict[str, Any]:
    """T2.22a — RTL synth slice + full pipeline stimulus (pre-mapped netlist)."""
    sim = _run_synth_slice_rtl_tb(backend=backend)
    ticks = _parse_rtl_mapped_pose(sim["stdout"])
    return {
        "backend": sim["backend"],
        "status": sim["status"],
        "tick_count": len(ticks),
        "ticks": ticks,
        "stdout_tail": sim["stdout_tail"],
        "sim_layer": "rtl_synth_slice_pipeline",
    }


def run_iron_world_motion_mapped_alu_mmio_sim(*, backend: str = "auto") -> dict[str, Any]:
    """H1 — full ALU mapped netlist + MMIO φ-FSM world motion."""
    sim = _run_mapped_alu_mmio_tb(backend=backend)
    ticks = _parse_rtl_world_pose(sim["stdout"])
    return {
        "backend": sim["backend"],
        "status": sim["status"],
        "tick_count": len(ticks),
        "ticks": ticks,
        "stdout_tail": sim["stdout_tail"],
        "sim_layer": sim.get("sim_layer", "mapped_full_alu_mmio"),
    }


def run_iron_world_motion_mapped_slice_sim(*, backend: str = "auto") -> dict[str, Any]:
    """Nangate45 mapped geo_prod ex_pipe — structural netlist smoke."""
    sim = _run_mapped_slice_tb(backend=backend)
    ticks = _parse_rtl_mapped_pose(sim["stdout"])
    return {
        "backend": sim["backend"],
        "status": sim["status"],
        "tick_count": len(ticks),
        "ticks": ticks,
        "stdout_tail": sim["stdout_tail"],
        "sim_layer": sim.get("sim_layer", "mapped_netlist_slice"),
    }


if __name__ == "__main__":
    import json

    r = run_iron_world_motion_sim()
    print(json.dumps({"status": r["status"], "ticks": r["tick_count"], "backend": r["backend"]}, indent=2))
