# Contributing to DroidRecon

First off, thank you for taking the time to contribute. All contributions are welcome — bug fixes, new features, documentation improvements, and ideas.

## Before You Start

- Check existing [Issues](../../issues) and [Pull Requests](../../pulls) to avoid duplicates
- For large changes, open an issue first to discuss the approach before investing time in a PR
- All contributions must be for **authorized security testing and educational purposes**

## Development Setup

```bash
git clone https://github.com/ThiagoShade/droidrecon.git
cd droidrecon

# Build the image locally
docker build -t droidrecon-dev .

# Run for testing
docker run -d --name droidrecon-dev \
  -p 8000:8000 \
  -v apk-dev:/apks \
  -v mobsf-dev:/home/mobsf/.MobSF \
  droidrecon-dev
```

## How to Contribute

### Reporting Bugs

Use the [bug report template](.github/ISSUE_TEMPLATE/bug_report.md). Include:
- Docker version and host OS
- Exact command that failed
- Full error output
- Container logs (`docker logs droidrecon`)

### Suggesting Features

Use the [feature request template](.github/ISSUE_TEMPLATE/feature_request.md). Check the [Roadmap](README.md#roadmap) first — your idea may already be planned.

### Submitting Pull Requests

1. Fork the repository and create a branch from `main`
2. Make your changes — keep PRs focused on a single concern
3. Test your changes by running a full analysis end-to-end
4. Update the README if you've changed CLI flags, behavior, or the architecture
5. Submit the PR with a clear description of what and why

## Code Guidelines

- **orchestrator/analyze.py** — keep it standard-library-only where possible (except `requests`, which MobSF already provides); no new dependencies without discussion
- **Dockerfile** — each `RUN` instruction that installs packages must clean up caches in the same layer
- **entrypoint.sh** — keep startup logic minimal; complexity belongs in the orchestrator
- No print statements without the `[*]` / `[+]` / `[-]` / `[!]` prefix convention

## Commit Messages

Use imperative mood and keep the first line under 72 characters:

```
Add batch analysis support for package list files
Fix base APK detection when all splits share the same name prefix
Update README with armv7 architecture example
```

## License

By contributing, you agree your work will be licensed under the [GPL-3.0 License](LICENSE).
