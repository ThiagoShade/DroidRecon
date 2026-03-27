#!/usr/bin/env python3
"""
APK Static Analyzer - Orchestrator CLI

Downloads Android APKs from Google Play and runs MobSF static analysis.
Designed for Red Team enumeration pipelines.

Usage:
    analyze com.example.appname
    analyze com.example.appname --no-pdf
    analyze com.example.appname --no-scan
    analyze com.example.appname --arch armv7
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

GPLAY_DIR = Path("/opt/gplay")
GPLAY_CLI = str(GPLAY_DIR / "gplay")
GPLAY_TEMP_OUTPUT = Path("/tmp/gplay_dl")
DEFAULT_APK_DIR = Path("/apks")
DEFAULT_MOBSF_URL = "http://127.0.0.1:8000"
MOBSF_SECRET_PATH = Path("/home/mobsf/.MobSF/secret")


# ---------------------------------------------------------------------------
# MobSF API key
# ---------------------------------------------------------------------------

def get_mobsf_api_key():
    """Read MobSF API key from env or derive from secret file."""
    api_key = os.environ.get("MOBSF_API_KEY")
    if api_key:
        return api_key
    if MOBSF_SECRET_PATH.exists():
        secret = MOBSF_SECRET_PATH.read_text().strip()
        return hashlib.sha256(secret.encode()).hexdigest()
    print("[-] Could not determine MobSF API key", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# gplay-apk-downloader helpers
# ---------------------------------------------------------------------------

def run_gplay(args, timeout=300):
    """Run a gplay CLI command and return the CompletedProcess."""
    cmd = [GPLAY_CLI] + args
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(GPLAY_DIR),
    )


def ensure_auth():
    """Authenticate with Google Play via AuroraOSS anonymous dispenser."""
    print("[*] Authenticating with Google Play...")
    result = run_gplay(["auth"], timeout=60)
    if result.returncode != 0:
        # Retry once - sometimes the first attempt fails due to rate limiting
        print("[!] First auth attempt failed, retrying...")
        result = run_gplay(["auth"], timeout=60)
        if result.returncode != 0:
            print(f"[-] Authentication failed: {result.stderr.strip()}", file=sys.stderr)
            sys.exit(1)
    print("[+] Authenticated successfully")


def download_apk(package, arch="arm64"):
    """Download APK splits via gplay CLI. Returns list of downloaded APK Paths."""
    # Clean previous temp output to avoid mixing downloads from different packages
    if GPLAY_TEMP_OUTPUT.exists():
        shutil.rmtree(GPLAY_TEMP_OUTPUT)
    GPLAY_TEMP_OUTPUT.mkdir(parents=True, exist_ok=True)

    print(f"[*] Downloading {package} (arch: {arch})...")
    # Correct flags: package positional first, then -a/--arch and -o/--output
    result = run_gplay(
        ["download", package, "--arch", arch, "--output", str(GPLAY_TEMP_OUTPUT)],
        timeout=300,
    )

    if result.returncode != 0:
        stderr = result.stderr.strip()
        stdout = result.stdout.strip()
        print(f"[-] Download failed", file=sys.stderr)
        if stderr:
            print(f"    stderr: {stderr}", file=sys.stderr)
        if stdout:
            print(f"    stdout: {stdout}", file=sys.stderr)
        sys.exit(1)

    # Find all APK files in the output tree
    apk_files = sorted(GPLAY_TEMP_OUTPUT.rglob("*.apk"))
    if not apk_files:
        print("[-] No APK files found after download", file=sys.stderr)
        print(f"    gplay stdout: {result.stdout.strip()}", file=sys.stderr)
        sys.exit(1)

    print(f"[+] Downloaded {len(apk_files)} APK file(s)")
    return apk_files


def identify_base_apk(apk_files):
    """Identify the base APK from a list of split APK files.

    The base APK is the main application code. Config splits (locale, DPI,
    ABI) are excluded. The base is typically the largest non-config APK.
    """
    candidates = []
    for apk in apk_files:
        name_lower = apk.name.lower()
        # Exclude config/split APKs by common naming patterns
        if any(pattern in name_lower for pattern in [
            "config.", "split_config", "split.", ".config.",
            "xxxhdpi", "xxhdpi", "xhdpi", "hdpi", "mdpi",
            "arm64", "armeabi", "x86",
        ]):
            continue
        candidates.append(apk)

    if candidates:
        # Return the largest candidate
        return max(candidates, key=lambda p: p.stat().st_size)

    # Fallback: just return the largest APK overall
    return max(apk_files, key=lambda p: p.stat().st_size)


def save_apks(apk_files, package, output_dir):
    """Move all downloaded APK files to /apks/<package>/."""
    pkg_dir = output_dir / package
    pkg_dir.mkdir(parents=True, exist_ok=True)

    saved = []
    for apk in apk_files:
        dest = pkg_dir / apk.name
        shutil.move(str(apk), dest)
        saved.append(dest)
        size_mb = dest.stat().st_size / (1024 * 1024)
        print(f"    {apk.name} ({size_mb:.1f} MB)")

    # Clean up temp download directory
    shutil.rmtree(GPLAY_TEMP_OUTPUT, ignore_errors=True)

    return saved


# ---------------------------------------------------------------------------
# MobSF API helpers
# ---------------------------------------------------------------------------

def wait_for_mobsf(url, api_key, timeout=120):
    """Poll MobSF until it responds, up to `timeout` seconds."""
    import requests

    print("[*] Waiting for MobSF to be ready...")
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(
                f"{url}/api/v1/scans",
                headers={"X-Mobsf-Api-Key": api_key},
                timeout=5,
            )
            if r.status_code == 200:
                print("[+] MobSF is ready")
                return True
        except Exception:
            pass
        time.sleep(2)

    print(f"[-] MobSF did not become ready within {timeout}s", file=sys.stderr)
    return False


def upload_to_mobsf(apk_path, url, api_key):
    """Upload an APK file to MobSF. Returns the response dict with 'hash'."""
    import requests

    print(f"[*] Uploading {apk_path.name} to MobSF...")
    with open(apk_path, "rb") as f:
        r = requests.post(
            f"{url}/api/v1/upload",
            files={"file": (apk_path.name, f, "application/octet-stream")},
            headers={"X-Mobsf-Api-Key": api_key},
        )
    if r.status_code != 200:
        print(f"[-] Upload failed: HTTP {r.status_code}", file=sys.stderr)
        print(f"    {r.text}", file=sys.stderr)
        sys.exit(1)

    data = r.json()
    print(f"[+] Uploaded. Hash: {data.get('hash', 'N/A')}")
    return data


def trigger_scan(file_hash, url, api_key):
    """Trigger MobSF static analysis. Blocks until analysis completes."""
    import requests

    print("[*] Running static analysis (this may take several minutes)...")
    r = requests.post(
        f"{url}/api/v1/scan",
        data={"hash": file_hash},
        headers={"X-Mobsf-Api-Key": api_key},
        timeout=3600,
    )
    if r.status_code != 200:
        print(f"[-] Scan failed: HTTP {r.status_code}", file=sys.stderr)
        print(f"    {r.text}", file=sys.stderr)
        sys.exit(1)

    print("[+] Static analysis complete")
    return r.json()


def get_json_report(file_hash, url, api_key):
    """Retrieve the full JSON analysis report from MobSF."""
    import requests

    r = requests.post(
        f"{url}/api/v1/report_json",
        data={"hash": file_hash},
        headers={"X-Mobsf-Api-Key": api_key},
    )
    r.raise_for_status()
    return r.json()


def get_pdf_report(file_hash, url, api_key):
    """Download the PDF analysis report from MobSF."""
    import requests

    r = requests.post(
        f"{url}/api/v1/download_pdf",
        data={"hash": file_hash},
        headers={"X-Mobsf-Api-Key": api_key},
        timeout=120,
    )
    r.raise_for_status()
    return r.content


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def print_summary(report, package, output_dir, file_hash, mobsf_url):
    """Print a human-readable summary of analysis results."""
    print()
    print("=" * 60)
    print(f"  ANALYSIS SUMMARY: {package}")
    print("=" * 60)

    for field, label in [
        ("app_name", "App Name"),
        ("version_name", "Version"),
        ("package_name", "Package"),
        ("target_sdk", "Target SDK"),
        ("min_sdk", "Min SDK"),
    ]:
        if field in report:
            print(f"  {label + ':':<16}{report[field]}")

    # Security score (location varies by MobSF version)
    appsec = report.get("appsec", {})
    if "security_score" in appsec:
        print(f"  {'Security:':<16}{appsec['security_score']}/100")

    # Count findings by severity
    code_analysis = report.get("code_analysis", {})
    if isinstance(code_analysis, dict):
        severity_counts = {}
        for finding in code_analysis.values():
            if isinstance(finding, dict):
                meta = finding.get("metadata", {})
                sev = meta.get("severity", "info") if isinstance(meta, dict) else "info"
                severity_counts[sev] = severity_counts.get(sev, 0) + 1
        if severity_counts:
            parts = [f"{sev}: {count}" for sev, count in sorted(severity_counts.items())]
            print(f"  {'Findings:':<16}{', '.join(parts)}")

    # Permissions count
    permissions = report.get("permissions", {})
    if permissions:
        print(f"  {'Permissions:':<16}{len(permissions)} declared")

    print()
    print(f"  APK Files:    {output_dir / package}/")
    print(f"  Scan Hash:    {file_hash}")
    print(f"  MobSF GUI:    {mobsf_url}")
    print("=" * 60)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="APK Static Analyzer - Download and analyze Android apps",
        epilog="Example: analyze com.example.app",
    )
    parser.add_argument(
        "package",
        help="Android package name (e.g., com.example.app)",
    )
    parser.add_argument(
        "--arch", "-a",
        default="arm64",
        choices=["arm64", "armv7"],
        help="CPU architecture (default: arm64)",
    )
    parser.add_argument(
        "--output-dir", "-o",
        type=Path,
        default=DEFAULT_APK_DIR,
        help=f"APK output directory (default: {DEFAULT_APK_DIR})",
    )
    parser.add_argument(
        "--no-scan",
        action="store_true",
        help="Download APK only, skip MobSF analysis",
    )
    parser.add_argument(
        "--no-pdf",
        action="store_true",
        help="Skip PDF report generation",
    )
    parser.add_argument(
        "--no-json",
        action="store_true",
        help="Skip JSON report generation",
    )
    parser.add_argument(
        "--mobsf-url",
        default=os.environ.get("MOBSF_URL", DEFAULT_MOBSF_URL),
        help=f"MobSF API URL (default: {DEFAULT_MOBSF_URL})",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="Max seconds to wait for MobSF readiness (default: 120)",
    )

    args = parser.parse_args()

    print()
    print("[*] APK Static Analyzer")
    print(f"[*] Target: {args.package}")
    print()

    # --- Step 1: Authenticate with Google Play ---
    ensure_auth()

    # --- Step 2: Download APK splits ---
    apk_files = download_apk(args.package, args.arch)

    # --- Step 3: Identify the base APK ---
    base_apk = identify_base_apk(apk_files)
    print(f"[*] Base APK identified: {base_apk.name}")

    # --- Step 4: Save all APKs to output directory ---
    print(f"[*] Saving APKs to {args.output_dir / args.package}/")
    save_apks(apk_files, args.package, args.output_dir)
    base_apk_saved = args.output_dir / args.package / base_apk.name

    if args.no_scan:
        print(f"\n[+] Download complete. APKs saved to {args.output_dir / args.package}/")
        return

    # --- Step 5: MobSF integration ---
    api_key = get_mobsf_api_key()

    if not wait_for_mobsf(args.mobsf_url, api_key, args.timeout):
        sys.exit(1)

    # --- Step 6: Upload base APK to MobSF ---
    upload_data = upload_to_mobsf(base_apk_saved, args.mobsf_url, api_key)
    file_hash = upload_data["hash"]

    # --- Step 7: Trigger static analysis ---
    trigger_scan(file_hash, args.mobsf_url, api_key)

    # --- Step 8: Generate reports ---
    pkg_dir = args.output_dir / args.package
    report = {}

    if not args.no_json:
        print("[*] Generating JSON report...")
        report = get_json_report(file_hash, args.mobsf_url, api_key)
        json_path = pkg_dir / "report.json"
        with open(json_path, "w") as f:
            json.dump(report, f, indent=2)
        print(f"[+] JSON report saved: {json_path}")

    if not args.no_pdf:
        print("[*] Generating PDF report...")
        pdf_data = get_pdf_report(file_hash, args.mobsf_url, api_key)
        pdf_path = pkg_dir / "report.pdf"
        with open(pdf_path, "wb") as f:
            f.write(pdf_data)
        print(f"[+] PDF report saved: {pdf_path}")

    # --- Step 9: Print summary ---
    if not report and not args.no_json:
        report = get_json_report(file_hash, args.mobsf_url, api_key)

    print_summary(
        report if report else {},
        args.package,
        args.output_dir,
        file_hash,
        args.mobsf_url,
    )


if __name__ == "__main__":
    main()
