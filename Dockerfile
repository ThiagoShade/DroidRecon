FROM opensecurity/mobile-security-framework-mobsf:latest

USER root

# Install additional system dependencies
# gosu is used in the entrypoint to fix volume permissions then drop to mobsf user
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    gosu \
    && rm -rf /var/lib/apt/lists/*

# Clone gplay-apk-downloader (shallow clone to avoid full git history)
RUN git clone --depth 1 https://github.com/alltechdev/gplay-apk-downloader.git /opt/gplay && \
    rm -rf /opt/gplay/.git

# Create isolated Python venv for gplay to avoid protobuf version conflict with MobSF.
# (gplay requires protobuf>=3.19,<4.0 while MobSF may use protobuf 4+)
# We use gplay as a CLI tool only, so web-server packages (flask, gunicorn, gevent)
# are uninstalled after to reduce image size.
RUN python3 -m venv /opt/gplay/.venv && \
    /opt/gplay/.venv/bin/pip install --no-cache-dir -r /opt/gplay/requirements.txt && \
    /opt/gplay/.venv/bin/pip uninstall -y flask flask-cors gunicorn gevent psutil && \
    /opt/gplay/.venv/bin/pip cache purge

# Make gplay CLI executable
RUN chmod +x /opt/gplay/gplay /opt/gplay/gplay-downloader.py

# Generate debug keystore for APK operations (used by gplay if merging)
RUN mkdir -p /home/mobsf/.android && \
    keytool -genkey -v -keystore /home/mobsf/.android/debug.keystore \
      -storepass android -alias androiddebugkey -keypass android \
      -keyalg RSA -keysize 2048 -validity 10000 \
      -dname "CN=Android Debug,O=Android,C=US" 2>/dev/null || true

# Copy orchestrator CLI
COPY orchestrator/ /opt/orchestrator/
RUN chmod +x /opt/orchestrator/analyze.py && \
    ln -sf /opt/orchestrator/analyze.py /usr/local/bin/analyze

# Create APK output directory
RUN mkdir -p /apks

# Fix ownership for all custom directories
RUN chown -R mobsf:mobsf /opt/gplay /opt/orchestrator /apks /home/mobsf/.android

# Copy custom entrypoint wrapper
COPY entrypoint.sh /entrypoint-wrapper.sh
RUN chmod +x /entrypoint-wrapper.sh

VOLUME ["/apks"]

# Keep root as the default user so the entrypoint can fix volume mount permissions.
# The entrypoint drops to the mobsf user via gosu before starting MobSF.

ENTRYPOINT ["/entrypoint-wrapper.sh"]
