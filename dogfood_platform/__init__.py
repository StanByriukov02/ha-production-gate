"""Dogfood platform foundation — F1 fidelity · F5 receipts · F2 scheduler."""

# HARD (win32): block console-flash children process-wide before any spawn path.
from dogfood_platform.win_hidden_subprocess_v1 import (  # noqa: E402
    install_global_no_console_flash,
)

install_global_no_console_flash()

from dogfood_platform.fidelity import (
    EpsilonSlot,
    FidelityContract,
    PhysicsHop,
    RegionTag,
    w0_default_contract,
)
from dogfood_platform.receipts import ExperimentReceipt, ReceiptStore
from dogfood_platform.scheduler import ChainRun, SchedulerShell, StageSpec
from dogfood_platform.stages_w0 import w0_default_workload, w0_mock_stage_specs

__all__ = [
    "ChainRun",
    "EpsilonSlot",
    "ExperimentReceipt",
    "FidelityContract",
    "PhysicsHop",
    "ReceiptStore",
    "RegionTag",
    "SchedulerShell",
    "StageSpec",
    "w0_default_contract",
    "w0_default_workload",
    "w0_mock_stage_specs",
]
