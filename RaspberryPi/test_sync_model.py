"""
test_sync_model_simulation.py – Simulates periodic model sync checks
=====================================================================

Polls a (mocked or real) server repeatedly with a configurable delay,
printing a clean one-line result per attempt.

Usage:
    python test_sync_model_simulation.py                        # mock mode
    python test_sync_model_simulation.py --server http://192.168.1.100:5000  # real server
    python test_sync_model_simulation.py --attempts 5 --delay 3
    python test_sync_model_simulation.py --simulate-updates     # mock version bumps
"""

import os
import sys
import time
import json
import argparse
import shutil
import tempfile
from unittest.mock import patch
import io

# ──────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ──────────────────────────────────────────────────────────────────────────────

DEFAULT_SERVER_URL     = None          # None = mock mode, set to real URL for live test
DEFAULT_MODEL_DIR      = os.path.join(os.path.dirname(__file__), "models")
DEFAULT_DELAY_SECONDS  = 2.0          # seconds between sync attempts
DEFAULT_ATTEMPTS       = 10           # how many sync polls to run
SIMULATE_UPDATE_EVERY  = 3            # in mock mode: bump server version every N attempts

# ──────────────────────────────────────────────────────────────────────────────

DUMMY_WEIGHTS = b"\x80\x04\x95\x0e\x00\x00\x00\x00\x00\x00\x00\x8c\x05torch\x94."

GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
BOLD   = "\033[1m"
RESET  = "\033[0m"


# ──────────────────────────────────────────────────────────────────────────────
# MOCK SERVER
# ──────────────────────────────────────────────────────────────────────────────

class MockServer:
    """Simulates the Flask server version and download endpoints."""

    def __init__(self, start_version: int = 1):
        self.version = start_version

    def bump(self):
        self.version += 1

    def urlopen(self, url: str, timeout: int = 15):
        if "version" in url:
            data = json.dumps({"version": self.version}).encode()
        elif "download" in url:
            data = DUMMY_WEIGHTS
        else:
            raise ValueError(f"Unknown mock URL: {url}")

        stream = io.BytesIO(data)

        class _Resp:
            def __enter__(self_): return self_
            def __exit__(self_, *a): pass
            def read(self_, *a): return stream.read(*a)
            def readinto(self_, buf): return stream.readinto(buf)

        return _Resp()


# ──────────────────────────────────────────────────────────────────────────────
# SIMULATION
# ──────────────────────────────────────────────────────────────────────────────

def run_simulation(
    server_url: str | None,
    model_dir: str,
    delay: float,
    attempts: int,
    simulate_updates: bool,
) -> None:

    try:
        import sync_model as sm
    except ImportError:
        print(f"{RED}[ERROR]{RESET} Cannot import sync_model.py — make sure it's in the same directory.")
        sys.exit(1)

    mock_mode = server_url is None
    mock      = MockServer(start_version=1) if mock_mode else None

    # Use a temp dir in mock mode so we don't touch real model files
    if mock_mode:
        model_dir = tempfile.mkdtemp(prefix="sync_sim_")

    print(f"{BOLD}{'─'*55}{RESET}")
    print(f"  SYNC MODEL SIMULATION")
    print(f"{'─'*55}")
    print(f"  Mode      : {'MOCK' if mock_mode else 'LIVE'}")
    if mock_mode:
        print(f"  Mock dir  : {model_dir}")
        print(f"  Updates   : {'every ' + str(SIMULATE_UPDATE_EVERY) + ' attempts' if simulate_updates else 'disabled'}")
    else:
        print(f"  Server    : {server_url}")
        print(f"  Model dir : {model_dir}")
    print(f"  Attempts  : {attempts}  |  Delay: {delay}s")
    print(f"{'─'*55}")
    print(f"  {'#':>3}  {'Time':>8}  {'Local':>6}  {'Server':>7}  {'Result'}")
    print(f"  {'─'*3}  {'─'*8}  {'─'*6}  {'─'*7}  {'─'*20}")

    updated_count  = 0
    skipped_count  = 0
    error_count    = 0

    try:
        for attempt in range(1, attempts + 1):

            # Bump mock server version on schedule
            if mock_mode and simulate_updates and attempt > 1 and (attempt - 1) % SIMULATE_UPDATE_EVERY == 0:
                mock.bump()

            local_ver  = sm._local_version(model_dir)
            timestamp  = time.strftime("%H:%M:%S")

            try:
                if mock_mode:
                    with patch("urllib.request.urlopen", side_effect=mock.urlopen):
                        updated = sm.sync_if_needed(
                            server_url="http://mock-server:5000",
                            model_dir=model_dir,
                        )
                else:
                    updated = sm.sync_if_needed(
                        server_url=server_url,
                        model_dir=model_dir,
                    )

                server_ver = sm._local_version(model_dir) if updated else local_ver
                if mock_mode:
                    server_ver = mock.version

                if updated:
                    updated_count += 1
                    status = f"{GREEN}✓ UPDATED  → v{sm._local_version(model_dir)}{RESET}"
                else:
                    skipped_count += 1
                    status = f"  up-to-date (v{local_ver})"

            except RuntimeError as e:
                error_count += 1
                server_ver = "?"
                status = f"{RED}✗ ERROR: {str(e)[:35]}{RESET}"

            print(f"  {attempt:>3}  {timestamp}  v{local_ver:<5}  v{server_ver:<6}  {status}")

            if delay > 0 and attempt < attempts:
                time.sleep(delay)

    finally:
        if mock_mode:
            shutil.rmtree(model_dir, ignore_errors=True)

    print(f"{'─'*55}")
    print(f"  Done — {attempts} attempts  |  "
          f"{GREEN}{updated_count} updated{RESET}  |  "
          f"{skipped_count} skipped  |  "
          f"{RED if error_count else ''}{error_count} errors{RESET if error_count else ''}")
    print(f"{'─'*55}\n")


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Simulate periodic sync_model polling against a real or mocked server."
    )
    parser.add_argument(
        "--server",
        type=str,
        default=DEFAULT_SERVER_URL,
        help="Server base URL (e.g. http://192.168.1.100:5000). Omit for mock mode."
    )
    parser.add_argument(
        "--model-dir",
        type=str,
        default=DEFAULT_MODEL_DIR,
        help="Local model directory (ignored in mock mode)."
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY_SECONDS,
        help=f"Seconds between sync attempts (default: {DEFAULT_DELAY_SECONDS})."
    )
    parser.add_argument(
        "--attempts",
        type=int,
        default=DEFAULT_ATTEMPTS,
        help=f"Total number of sync attempts (default: {DEFAULT_ATTEMPTS})."
    )
    parser.add_argument(
        "--simulate-updates",
        action="store_true",
        help=f"In mock mode: bump server version every {SIMULATE_UPDATE_EVERY} attempts."
    )

    args = parser.parse_args()

    run_simulation(
        server_url=args.server,
        model_dir=args.model_dir,
        delay=args.delay,
        attempts=args.attempts,
        simulate_updates=args.simulate_updates,
    )


if __name__ == "__main__":
    main()