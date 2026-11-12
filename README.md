# Agent Build Environment

An interactive console for creating an agent build environment on **Agent Substrate** with **AX (Agent Executor)** — configure an agent in a **gVisor** or **MicroVM** sandbox and generate everything needed to run it for real.

**Live page:** https://vexdz911-blip.github.io/agent-build-environment/

## What it does

- **Configurator** — agent name, sandbox class (gVisor or MicroVM), kind or existing cluster, base image, CPU/memory, replicas (1/2/3/5), network policy, snapshots, autoscaling and night-suspend.
- **Live-generated files** — `ax.yaml`, `substrate.yaml`, `commands.sh`, `Dockerfile`, `main.tf` (Terraform), `Pulumi.ts`, plus a six-stage dry-run pipeline simulation and a tailored `preflight.sh`.
- **Starter templates** — First Agent, Coding Agent, Browser/Research Agent, CI Build Agent, Untrusted Code Runner — and a downloadable starter bundle (ZIP) with runbooks, a GitHub Actions workflow, and a generated Playwright test.
- **Operational tooling** — cluster capability scan (download the scanner, paste results back), multi-agent topologies, readiness checks with one-click fixes, cost estimator, failure drills, and an error decoder.
- **For agents & tools** — an MCP tool manifest generated from the spec, a versioned JSON Schema (`abe-spec` v1) with a built-in validator, a postMessage embed API, an agent handoff packet, SHA-256 checksum manifests in every ZIP, and a deterministic output mode.

The page is a single self-contained HTML file with no build step and no server: open `index.html` locally or serve it from any static host. All state stays in your browser (localStorage); nothing is sent anywhere.

## Verification note

The console's load, render, layout, and default-state consistency are checked. Click-level interaction proof is provided by the Playwright test the page itself generates (`agent-build.spec.ts` in the starter bundle): run it against the live page URL for real pass/fail results.

## Deployment

This repository is published with GitHub Pages via the workflow in `.github/workflows/pages.yml`, which deploys the repository root on every push to `main`.

## Diagrams (Mermaid API)

Diagram sources live in `diagrams/` as Mermaid code (`.mmd`) and are rendered to SVG with the [Mermaid API](https://api.mermaid.ai/v1/docs) by `tools/render-mermaid.py` — no local Mermaid install needed.

```bash
export MERMAID_API_KEY=<your key>     # read from the environment only —
                                      # never commit it or put it in a file
python3 tools/render-mermaid.py --balance                  # free: balance + endpoint costs
python3 tools/render-mermaid.py diagrams/architecture.mmd  # writes diagrams/architecture.svg
```

How it behaves:

- The key is read from the `MERMAID_API_KEY` environment variable and sent only as the `Authorization: Bearer` header. It never appears in code, config, logs, or output.
- Every run checks `GET /v1/balance` first (free). Before a batch it estimates the total cost and refuses to start if the remaining balance can't cover it.
- Each diagram is validated before rendering: validation costs 1 credit, a render 5 — and a diagram the parser refuses *at render time* still costs the full 5, so invalid diagrams are caught at the validate step and never sent to the renderer.
- Requests refused before any work (missing/invalid key, malformed body) cost nothing.
- Output lands next to the source (`architecture.mmd` → `architecture.svg`); `--format png|pdf` and `--out DIR` are supported.

