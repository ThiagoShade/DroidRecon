#!/bin/bash
set -e

MOBSF_USER=mobsf

# Fix ownership of volume-mounted directories.
# When Docker creates a named volume for the first time it may be owned by root,
# which prevents the mobsf user from writing to it.
echo "[*] Fixing volume permissions..."
chown -R "${MOBSF_USER}:${MOBSF_USER}" /home/mobsf/.MobSF /apks 2>/dev/null || true

# Pre-authenticate gplay-apk-downloader as the mobsf user (best-effort).
echo "[*] Pre-authenticating gplay-apk-downloader..."
gosu "${MOBSF_USER}" /opt/gplay/gplay auth 2>/dev/null \
  || echo "[!] gplay pre-auth failed (will retry on first use)"

# Drop privileges and exec MobSF's original entrypoint.
exec gosu "${MOBSF_USER}" /home/mobsf/Mobile-Security-Framework-MobSF/scripts/entrypoint.sh
