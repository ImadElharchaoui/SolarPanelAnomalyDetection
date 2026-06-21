"""
sync_model.py - Raspberry Pi Model Synchronization Utility
===========================================================

Polls the web server for the latest model version and, if a newer
version is available, downloads the updated weights and atomically
replaces the local checkpoint.

Usage (standalone / cron):
    python sync_model.py --server-url http://<SERVER_IP>:5000 --model-dir ./models

Usage (imported by daily_check or other scripts):
    from sync_model import sync_if_needed
    updated = sync_if_needed("http://192.168.1.100:5000", "./models")
    if updated:
        print("Model updated - reload artifacts before inference.")

Cron example (every hour):
    0 * * * * /usr/bin/python3 /home/pi/sync_model.py \
        --server-url http://192.168.1.100:5000 \
        --model-dir /home/pi/models >> /var/log/sync_model.log 2>&1
"""

import os
import sys
import json
import shutil
import argparse
import traceback

# ---------------------------------------------------------------------------
# Version file helpers
# ---------------------------------------------------------------------------

VERSION_FILENAME = "model_version.txt"


def _local_version(model_dir: str) -> int:
    """Returns the locally cached model version (0 if not yet recorded)."""
    version_path = os.path.join(model_dir, VERSION_FILENAME)
    if not os.path.exists(version_path):
        return 0
    try:
        with open(version_path, "r", encoding="utf-8") as f:
            return int(f.read().strip())
    except (ValueError, IOError):
        return 0


def _save_local_version(model_dir: str, version: int) -> None:
    """Persists the downloaded version number to disk."""
    version_path = os.path.join(model_dir, VERSION_FILENAME)
    with open(version_path, "w", encoding="utf-8") as f:
        f.write(str(version))


# ---------------------------------------------------------------------------
# Core sync logic
# ---------------------------------------------------------------------------

def sync_if_needed(server_url: str, model_dir: str, timeout: int = 15) -> bool:
    """
    Checks the server for the current model version and downloads the
    weights file if a newer version exists.

    Args:
        server_url: Base URL of the Flask server, e.g. ``http://192.168.1.1:5000``.
        model_dir:  Local directory containing ``lstm_fault_detector.pth``.
        timeout:    HTTP request timeout in seconds (default 15).

    Returns:
        ``True`` if a new model was downloaded, ``False`` otherwise.

    Raises:
        RuntimeError: If the network request fails or the server returns
                      an unexpected response.
    """
    try:
        import urllib.request
        import urllib.error
    except ImportError:
        raise RuntimeError("urllib is not available in this Python environment.")

    server_url = server_url.rstrip("/")
    os.makedirs(model_dir, exist_ok=True)

    # ── 1. Query server version ────────────────────────────────────────────
    version_url = f"{server_url}/api/model/version"
    try:
        with urllib.request.urlopen(version_url, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        raise RuntimeError(f"Cannot reach version endpoint '{version_url}': {e}")
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Server returned invalid JSON from '{version_url}': {e}")

    server_version = int(payload.get("version", 1))
    local_version  = _local_version(model_dir)

    print(f"[sync_model] Local version: {local_version}  |  Server version: {server_version}")

    if server_version <= local_version:
        print("[sync_model] Model is already up-to-date. No download needed.")
        return False

    # ── 2. Download new weights ────────────────────────────────────────────
    download_url = f"{server_url}/api/model/download"
    weights_path = os.path.join(model_dir, "lstm_fault_detector.pth")
    tmp_path     = weights_path + ".tmp"

    print(f"[sync_model] Downloading model v{server_version} from '{download_url}' …")
    try:
        with urllib.request.urlopen(download_url, timeout=timeout) as resp:
            with open(tmp_path, "wb") as f_out:
                shutil.copyfileobj(resp, f_out)
    except urllib.error.URLError as e:
        # Clean up partial download
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise RuntimeError(f"Download failed from '{download_url}': {e}")

    # Validate that the downloaded file is a non-empty PyTorch checkpoint
    if os.path.getsize(tmp_path) == 0:
        os.remove(tmp_path)
        raise RuntimeError("Downloaded model weights file is empty.")

    # ── 3. Atomic replacement ──────────────────────────────────────────────
    # Rename is atomic on most POSIX filesystems; on Windows it may raise
    # OSError if the destination already exists - we handle that gracefully.
    try:
        os.replace(tmp_path, weights_path)
    except OSError:
        shutil.move(tmp_path, weights_path)

    # ── 4. Persist new version number ─────────────────────────────────────
    _save_local_version(model_dir, server_version)

    print(f"[sync_model] ✓ Model updated to version {server_version}. "
          f"Saved to '{weights_path}'.")
    return True


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Raspberry Pi Model Sync - downloads the latest model "
                    "weights from the Solar Panel web server if a new version "
                    "is available."
    )
    parser.add_argument(
        "--server-url",
        type=str,
        required=True,
        help="Base URL of the Flask web server (e.g. http://192.168.1.100:5000)."
    )
    parser.add_argument(
        "--model-dir",
        type=str,
        default=None,
        help="Local directory where model weights are stored. "
             "Defaults to './models' relative to this script."
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=15,
        help="HTTP request timeout in seconds (default: 15)."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output result as a machine-readable JSON object."
    )

    args = parser.parse_args()

    model_dir = args.model_dir or os.path.join(os.path.dirname(__file__), "raspberry", "models")

    try:
        updated = sync_if_needed(
            server_url=args.server_url,
            model_dir=model_dir,
            timeout=args.timeout
        )
        if args.json:
            print(json.dumps({"success": True, "updated": updated}))
        else:
            status = "updated" if updated else "already up-to-date"
            print(f"[sync_model] Done - model {status}.")

    except RuntimeError as e:
        if args.json:
            print(json.dumps({"success": False, "error": str(e)}))
        else:
            print(f"[sync_model] ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    except Exception:
        tb = traceback.format_exc()
        if args.json:
            print(json.dumps({"success": False, "error": tb}))
        else:
            print(tb, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
