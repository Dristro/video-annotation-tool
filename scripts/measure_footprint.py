#!/usr/bin/env python3
"""Measure the running app's memory/CPU footprint against a real project.

REQUIREMENT.md caps RAM at <4 GB and asks for smooth real-time playback;
BACKLOG.md noted the bounds (64 MiB demuxer cache, 8 MiB preload chunks)
were set but never *measured*. This script launches the app for real
(needs a display session -- it's a GUI), samples RSS and CPU via `ps`
once a second, and prints peak/average figures. Run it yourself against
your actual footage:

    .venv/bin/python scripts/measure_footprint.py --project ~/my-project --seconds 60

    # Or the bundled .app, exactly as users run it:
    .venv/bin/python scripts/measure_footprint.py --project ~/my-project \
        --command /Applications/VAT.app/Contents/MacOS/VAT

Interact with the app while it runs (play, scrub, step through the
playlist) -- the numbers only mean something for what you actually did.
`--auto-play` sends Space to the app after launch via AppleScript so an
unattended run at least plays the first video (requires Accessibility
permission for the terminal in System Settings).

`HOME` is left alone: opening the project through the app records it as
the last-opened project, the same as opening it by hand.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path


def sample(pid: int) -> tuple[float, float] | None:
    """(RSS in MiB, %CPU) for pid, or None once it has exited."""
    result = subprocess.run(["ps", "-o", "rss=,%cpu=", "-p", str(pid)], capture_output=True, text=True)
    parts = result.stdout.split()
    if len(parts) != 2:
        return None
    return int(parts[0]) / 1024.0, float(parts[1])


def send_space(pid: int) -> None:
    script = (
        f'tell application "System Events" to set frontmost of (first process whose unix id is {pid}) to true\n'
        'tell application "System Events" to keystroke " "'
    )
    subprocess.run(["osascript", "-e", script], capture_output=True, text=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project", required=True, help="project directory to open")
    parser.add_argument("--seconds", type=int, default=60, help="how long to sample (default 60)")
    parser.add_argument(
        "--command", default=None,
        help="executable to launch (default: the `vat` next to this interpreter, i.e. the venv's)",
    )
    parser.add_argument("--auto-play", action="store_true", help="press Space 5s after launch (AppleScript)")
    parser.add_argument("--keep", action="store_true", help="leave the app running when sampling ends")
    args = parser.parse_args()

    command = args.command or str(Path(sys.executable).with_name("vat"))
    if not shutil.which(command) and not Path(command).exists():
        print(f"not found: {command}", file=sys.stderr)
        return 2

    proc = subprocess.Popen([command, args.project])
    print(f"launched {command} (pid {proc.pid}); sampling for {args.seconds}s ...")
    samples: list[tuple[float, float, float]] = []  # (t, rss_mib, cpu)
    start = time.monotonic()
    played = False
    try:
        while time.monotonic() - start < args.seconds:
            time.sleep(1.0)
            elapsed = time.monotonic() - start
            if args.auto_play and not played and elapsed >= 5:
                send_space(proc.pid)
                played = True
            measured = sample(proc.pid)
            if measured is None:
                print(f"app exited after {elapsed:.0f}s (exit code {proc.poll()})")
                break
            rss, cpu = measured
            samples.append((elapsed, rss, cpu))
            print(f"  t={elapsed:5.0f}s  rss={rss:7.1f} MiB  cpu={cpu:5.1f}%")
    finally:
        if not args.keep and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(10)
            except subprocess.TimeoutExpired:
                proc.kill()

    if not samples:
        print("no samples collected")
        return 1
    peak_rss = max(s[1] for s in samples)
    avg_rss = sum(s[1] for s in samples) / len(samples)
    peak_cpu = max(s[2] for s in samples)
    avg_cpu = sum(s[2] for s in samples) / len(samples)
    print()
    print(f"RSS   peak {peak_rss:7.1f} MiB   avg {avg_rss:7.1f} MiB   (budget: < 4096 MiB)")
    print(f"CPU   peak {peak_cpu:6.1f} %     avg {avg_cpu:6.1f} %   (one core = 100%)")
    print("within RAM budget" if peak_rss < 4096 else "OVER RAM BUDGET")
    return 0


if __name__ == "__main__":
    sys.exit(main())
