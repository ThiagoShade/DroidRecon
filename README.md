<p align="center">
  <pre align="center">
  _____            _     _ _____                      
 |  __ \          (_)   | |  __ \                     
 | |  | |_ __ ___  _  __| | |__) |___  ___ ___  _ __  
 | |  | | '__/ _ \| |/ _` |  _  // _ \/ __/ _ \| '_ \ 
 | |__| | | | (_) | | (_| | | \ \  __/ (_| (_) | | | |
 |_____/|_|  \___/|_|\__,_|_|  \_\___|\___\___/|_| |_|
                                                                                       
  </pre>
  <b>Automated Android APK Static Analyzer for Red Team Operations</b>
  <br><br>
  <a href="#quick-start">Quick Start</a> &bull;
  <a href="#usage">Usage</a> &bull;
  <a href="#architecture">Architecture</a> &bull;
  <a href="#roadmap">Roadmap</a> &bull;
  <a href="#contributing">Contributing</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/platform-Docker-2496ED?logo=docker&logoColor=white" alt="Docker">
  <img src="https://img.shields.io/badge/analysis-MobSF-00C853" alt="MobSF">
  <img src="https://img.shields.io/badge/license-GPL--3.0-blue" alt="License">
  <img src="https://img.shields.io/badge/python-3.13-3776AB?logo=python&logoColor=white" alt="Python">
</p>

---

> **DroidRecon** automates the static security analysis of Android applications from the Google Play Store. Provide a package name, get a full MobSF security report. Designed to fit into Red Team enumeration pipelines with zero friction.

## Disclaimer

> **This tool is intended for authorized security testing, red team engagements, and educational purposes only.** Do not use this tool against applications without explicit written permission from the application owner. The authors are not responsible for any misuse or damage caused by this tool. Always follow applicable laws, regulations, and responsible disclosure practices.

## How It Works

DroidRecon chains two open source tools inside a single Docker container:

1. **[gplay-apk-downloader](https://github.com/alltechdev/gplay-apk-downloader)** - Downloads the target APK directly from Google Play using anonymous authentication (no Google account required)
2. **[MobSF](https://github.com/MobSF/Mobile-Security-Framework-MobSF)** - Performs comprehensive static analysis on the downloaded APK, covering OWASP Mobile Top 10, code analysis, manifest review, and more

The result: **one command** takes you from a package name to a full security report.

```
Package Name ──> Download APK ──> Static Analysis ──> JSON + PDF Reports
                  (gplay)           (MobSF)
```

## Features

- **Single command analysis** - Just provide the package name, everything else is automated
- **No Google account needed** - Uses anonymous Play Store authentication
- **Split APK handling** - Downloads all APK splits, identifies and analyzes the base APK
- **Persistent APK storage** - Downloaded APKs are kept for manual analysis with your own tools
- **MobSF Web GUI** - Full MobSF interface available on port 8000 for detailed review
- **JSON + PDF reports** - Machine-readable and shareable report formats
- **Pipeline-friendly** - CLI-first design with structured output for automation
- **Self-contained** - Everything runs in a single Docker container

## Quick Start

### Option 1: Build from source

```bash
git clone https://github.com/ThiagoShade/droidrecon.git
cd droidrecon
docker build -t droidrecon .
```

### Option 2: Pull from Docker Hub

```bash
docker pull docker.io/thiagoshade/droidrecon:latest
```

### Run the container

```bash
docker run -d --name droidrecon \
  -p 8000:8000 \
  -v apk-storage:/apks \
  -v mobsf-data:/home/mobsf/.MobSF \
  droidrecon
```

### Analyze your first target

```bash
docker exec droidrecon analyze com.example.app
```

## Usage

### Full analysis (JSON + PDF reports)

```bash
docker exec droidrecon analyze com.example.app
```

### Download APK only (no analysis)

```bash
docker exec droidrecon analyze com.example.app --no-scan
```

### JSON report only (skip PDF)

```bash
docker exec droidrecon analyze com.example.app --no-pdf
```

### Specify architecture

```bash
docker exec droidrecon analyze com.example.app --arch armv7
```

### CLI Reference

```
analyze <package_name> [options]

Positional:
  package              Android package name (e.g., com.example.app)

Options:
  --arch, -a           CPU architecture: arm64 | armv7 (default: arm64)
  --output-dir, -o     APK output directory (default: /apks)
  --no-scan            Download only, skip MobSF analysis
  --no-pdf             Skip PDF report generation
  --no-json            Skip JSON report generation
  --mobsf-url          MobSF API URL (default: http://127.0.0.1:8000)
  --timeout            Max seconds to wait for MobSF (default: 120)
```

### Accessing results

```bash
# List downloaded files
docker exec droidrecon ls /apks/com.example.app/

# Copy results to your host machine
docker cp droidrecon:/apks/com.example.app/ ./com.example.app/
```

### MobSF Web Interface

After starting the container, the full MobSF web GUI is available at:

```
http://localhost:8000
```

Default credentials: `mobsf` / `mobsf`

The web interface provides detailed interactive analysis including:
- Decompiled source code browsing
- Manifest analysis with permission mapping
- Network security configuration review
- Cryptographic issue detection
- Hardcoded secrets and API key detection

### Using with Docker Compose

```bash
docker compose up -d
docker exec droidrecon-apk-analyzer-1 analyze com.example.app
```

## Architecture

```
+-----------------------------------------------------------+
|                   Docker Container                        |
|                                                           |
|   +-------------------+     +-------------------------+   |
|   | gplay-downloader  |     |         MobSF           |   |
|   | (CLI, on-demand)  |     |   (Gunicorn :8000)      |   |
|   |                   |     |                         |   |
|   | - Anonymous auth  |     | - Static analysis       |   |
|   | - APK download    |     | - REST API              |   |
|   | - Split handling  |     | - Web GUI               |   |
|   +--------+----------+     | - PDF/JSON reports      |   |
|            |                +------------+------------+   |
|            v                             ^               |
|   +--------+-----------------------------+------------+   |
|   |              Orchestrator CLI                     |   |
|   |         /usr/local/bin/analyze                    |   |
|   |                                                   |   |
|   |  1. Auth with Play Store                          |   |
|   |  2. Download APK splits                           |   |
|   |  3. Identify base APK                             |   |
|   |  4. Upload to MobSF API                           |   |
|   |  5. Trigger static scan                           |   |
|   |  6. Generate reports                              |   |
|   +---------------------------------------------------+   |
|                         |                                 |
|                         v                                 |
|                   /apks/<package>/                         |
|                   +-- base.apk                            |
|                   +-- config.*.apk                        |
|                   +-- report.json                         |
|                   +-- report.pdf                          |
+-----------------------------------------------------------+
```

## Project Structure

```
droidrecon/
+-- Dockerfile              # Extends official MobSF image
+-- entrypoint.sh           # Volume permission fix + MobSF startup
+-- docker-compose.yml      # Convenience compose file
+-- orchestrator/
|   +-- analyze.py          # Main CLI orchestrator
+-- .dockerignore
+-- LICENSE
+-- CONTRIBUTING.md
+-- README.md
```

## Roadmap

DroidRecon is under active development. Here are planned improvements and ideas for community contributions:

### Ideas (Community Contributions Welcome)

- [ ] **Batch analysis** - Analyze multiple packages from a file list (`analyze --batch packages.txt`)
- [ ] **Version tracking** - Monitor apps for new versions and auto-analyze updates
- [ ] **SARIF export** - Output findings in SARIF format for integration with GitHub Security, DefectDojo, etc.
- [ ] **Comparison mode** - Diff two versions of the same app to identify security regressions
- [ ] **CI/CD integration** - GitHub Actions workflow for automated analysis on schedule
- [ ] **Notification hooks** - Slack/Discord/webhook notifications when analysis completes
- [ ] **MITRE ATT&CK mapping** - Map MobSF findings to Mobile ATT&CK techniques
- [ ] **Custom MobSF rules** - Bundled rule sets for common red team scenarios (banking apps, crypto wallets, etc.)
- [ ] **Frida script generation** - Auto-generate Frida hooks based on static analysis findings
- [ ] **Multi-format input** - Accept APK files directly, not just package names
- [ ] **HTML report template** - Branded standalone HTML report for client deliverables
- [ ] **Nuclei integration** - Feed discovered URLs/endpoints into Nuclei for further testing

See [CONTRIBUTING.md](CONTRIBUTING.md) to get started.

## Contributing

Contributions are welcome. Whether it's a bug fix, new feature, or documentation improvement, check out [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Credits

DroidRecon builds on top of excellent open source projects:

- **[MobSF](https://github.com/MobSF/Mobile-Security-Framework-MobSF)** by Ajin Abraham - Mobile Security Framework
- **[gplay-apk-downloader](https://github.com/alltechdev/gplay-apk-downloader)** by AllTechDev - Google Play APK downloader

## License

This project is licensed under the [GNU General Public License v3.0](LICENSE).

---

<p align="center">
  <sub>Built for the offensive security community.</sub>
</p>
