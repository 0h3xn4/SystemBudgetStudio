"""Run a full workflow of the installed program and show what it did on the network.

    python scripts/verify_offline.py [--budget PATH] [--gui PATH] [--keep DIR]

The workflow exports the examples, validates them, computes every budget with every report kind,
runs the scenario, the power timeline, the link passes and the beta sweep, compares two projects,
exchanges the spreadsheet tables, builds the user guide, runs the self-test, and with `--gui`
starts the window (`--smoke`). Every command must finish with a normal exit code (0, or 1 for a
finding the examples carry on purpose).

On Linux with `strace` every command runs under `strace -f -e trace=network`, and the run fails if
any command connects, sends or binds on an internet address (AF_INET or AF_INET6). Local sockets
(AF_UNIX, which Qt uses to talk to a display) are allowed. Before the workflow the detector is
checked against a command that really does connect, so a silent detector cannot pass. Without
strace (Windows, macOS) the workflow still runs and the OS-level checks of
docs/security-and-privacy.md apply (a firewall rule, a network monitor).

It is the evidence that the CI job `offline-evidence` keeps; anyone can run it on a machine with
the program installed. Nothing leaves the machine: it only starts the program's own commands.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

INTERNET = re.compile(r"sa_family=AF_INET6?\b")
NETWORK_CALLS = re.compile(r"\b(connect|sendto|sendmsg|sendmmsg|bind)\(")
NORMAL_EXIT = (0, 1)  # 1: a finding the examples carry on purpose (the program wrote its files)


def internet_calls(trace: str) -> list[str]:
    """The lines of an strace log that touch an internet address."""
    return [
        line for line in trace.splitlines() if NETWORK_CALLS.search(line) and INTERNET.search(line)
    ]


def traced(command: list[str], log: Path) -> list[str]:
    strace = shutil.which("strace")
    if strace is None:
        return command
    return [strace, "-f", "-qq", "-e", "trace=network", "-o", str(log), *command]


def detector_works(work: Path) -> bool:
    """A command that really connects (to the local machine, nothing leaves it) must be seen."""
    if shutil.which("strace") is None:
        return True
    log = work / "control.trace"
    code = (
        "import socket;s=socket.socket();s.settimeout(0.2)\n"
        "try: s.connect(('127.0.0.1', 9))\nexcept OSError: pass"
    )
    subprocess.run(traced([sys.executable, "-c", code], log), check=False, timeout=60)
    return bool(internet_calls(log.read_text(encoding="utf-8", errors="replace")))


def workflow(budget: str, work: Path) -> list[tuple[str, list[str]]]:
    demo, out = work / "demo", work / "out"
    eps, ex = str(demo / "microsat_250kg_eps"), str(demo / "microsat_250kg")
    tables = work / "tables"
    return [
        ("version", [budget, "--version"]),
        ("self-test", [budget, "self-test"]),
        ("export examples", [budget, "export-examples", str(demo)]),
        ("validate", [budget, "validate", eps]),
        ("budgets, every report kind", [budget, "run", ex, "--budget", "all", "--out", str(out)]),
        ("scenario", [budget, "scenario", eps, "--out", str(out)]),
        ("power timeline", [budget, "power-timeline", eps, "--out", str(out)]),
        ("link passes", [budget, "link-passes", str(demo / "microsat_150kg"), "--out", str(out)]),
        ("beta sweep", [budget, "thermal-beta", eps, "--out", str(out / "beta")]),
        ("explain", [budget, "explain", eps, "power:summary"]),
        ("compare", [budget, "compare", eps, ex, "--out", str(out / "compare")]),
        ("tables export", [budget, "tables-export", eps, "links", "--out", str(tables / "l.csv")]),
        ("tables import (dry run)", [budget, "tables-import", eps, "links", str(tables / "l.csv")]),
        ("user guide", [budget, "guide", "--out", str(work / "guide")]),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--budget", default=shutil.which("budget") or "budget")
    parser.add_argument("--gui", help="the window's program; started with --smoke")
    parser.add_argument("--keep", help="keep the traces and outputs in this folder")
    args = parser.parse_args()

    work = Path(args.keep) if args.keep else Path(tempfile.mkdtemp(prefix="sbs-offline-"))
    work.mkdir(parents=True, exist_ok=True)
    (work / "tables").mkdir(exist_ok=True)
    env = {**os.environ, "QT_QPA_PLATFORM": os.environ.get("QT_QPA_PLATFORM", "offscreen")}
    have_strace = shutil.which("strace") is not None
    note = "yes" if have_strace else "no (the workflow runs, the connections are not traced)"
    print(f"strace: {note}")
    if not detector_works(work):
        print("FAILED: the detector did not see a connection it should see", file=sys.stderr)
        return 2
    print("detector: sees a real connection" if have_strace else "detector: not used")

    steps = workflow(args.budget, work)
    if args.gui:
        steps.append(("window smoke test", [args.gui, "--smoke"]))
    failures: list[str] = []
    for number, (label, command) in enumerate(steps, start=1):
        log = work / f"{number:02d}.trace"
        result = subprocess.run(
            traced(command, log), env=env, capture_output=True, text=True, check=False, timeout=900
        )
        seen = (
            internet_calls(log.read_text(encoding="utf-8", errors="replace"))
            if log.is_file()
            else []
        )
        verdict = "ok" if result.returncode in NORMAL_EXIT and not seen else "FAILED"
        print(f"{verdict:6} {label} (exit {result.returncode}, internet calls {len(seen)})")
        if result.returncode not in NORMAL_EXIT:
            failures.append(f"{label}: exit {result.returncode}: {result.stderr.strip()[-300:]}")
        failures.extend(f"{label}: {line.strip()}" for line in seen[:5])
    if failures:
        print("\n".join(["", "FAILED:", *failures]), file=sys.stderr)
        return 1
    print(
        "\nNo command connected, sent or bound on an internet address."
        if have_strace
        else "\nEvery command finished; connections were not traced here."
    )
    if not args.keep:
        shutil.rmtree(work, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
