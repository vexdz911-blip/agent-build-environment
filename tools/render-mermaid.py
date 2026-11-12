#!/usr/bin/env python3
"""Render Mermaid diagrams to files through the Mermaid API (api.mermaid.ai).

The API key is read from the MERMAID_API_KEY environment variable. It is
never written to code, config, logs, or output — only sent as the
Authorization header of API requests.

Usage:
    export MERMAID_API_KEY=...            # your key, from your own vault/env
    python3 tools/render-mermaid.py diagrams/architecture.mmd
    python3 tools/render-mermaid.py --balance
    python3 tools/render-mermaid.py --format png diagrams/*.mmd

Costs (API credits, per the API's own /v1/balance pricing):
    balance check  0  (free, always safe)
    validate       1  per diagram — a failed render costs the full render
                        price, so every diagram is validated first and an
                        invalid one is never sent to the renderer
    render         5  per diagram

Requests refused before any work (bad/missing key, oversized body, malformed
JSON) cost nothing. Before a batch (more than one file) the script checks
/v1/balance and refuses to start if the remaining balance cannot cover the
batch. Rendered output is written next to each source file with the format's
extension (architecture.mmd -> architecture.svg), or into --out DIR.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

API_BASE = "https://api.mermaid.ai/v1"
COST_VALIDATE = 1
COST_RENDER = 5
EXTENSIONS = {"svg": ".svg", "png": ".png", "pdf": ".pdf"}


def api_key():
    key = os.environ.get("MERMAID_API_KEY")
    if not key:
        sys.exit(
            "MERMAID_API_KEY is not set. Export it in your shell first, e.g.\n"
            "  export MERMAID_API_KEY=<your key>\n"
            "The key is only ever read from the environment — it is not stored "
            "in this project."
        )
    return key


def call(method, path, key, body=None):
    """One API call. Returns (status, headers, bytes). Never logs the key."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        API_BASE + path,
        data=data,
        method=method,
        headers={
            "Authorization": "Bearer " + key,
            # No Accept: application/json on purpose for /render — the API
            # then returns the rendered bytes directly, ready to save.
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers or {}), e.read()
    except urllib.error.URLError as e:
        sys.exit(f"Could not reach the Mermaid API: {e.reason}")


def error_text(raw):
    try:
        err = json.loads(raw).get("error", {})
        msg = err.get("message", "")
        code = err.get("code", "")
        details = err.get("details") or {}
        pos = ""
        if details.get("line"):
            pos = f" (line {details['line']}, column {details.get('column', '?')})"
        return f"{code}: {msg}{pos}".strip(": ")
    except Exception:
        return raw.decode(errors="replace")[:300]


def get_balance(key):
    status, _, raw = call("GET", "/balance", key)
    if status != 200:
        sys.exit(f"Balance check failed — {error_text(raw)}")
    return json.loads(raw)


def show_balance(bal):
    print(
        "Balance: {remaining} credits remaining of {allowance} this month "
        "({spent} spent, resets {reset})".format(
            remaining=bal.get("remaining", "?"),
            allowance=bal.get("allowance", "?"),
            spent=bal.get("spent", "?"),
            reset=bal.get("resetAt", "?"),
        )
    )
    costs = bal.get("costs") or bal.get("endpointCosts") or []
    for c in costs:
        if isinstance(c, dict):
            print(
                "  cost: {ep} = {cost} credits".format(
                    ep=c.get("endpoint") or c.get("callClass") or "?",
                    cost=c.get("cost", "?"),
                )
            )


def validate(key, code):
    """Returns (valid, diagram_type, error_message). Costs 1 credit."""
    status, _, raw = call("POST", "/validate", key, {"code": code})
    if status != 200:
        return False, None, f"validate call failed — {error_text(raw)}"
    result = json.loads(raw)
    if result.get("valid"):
        return True, result.get("diagramType"), ""
    err = result.get("error") or {}
    msg = err.get("message", "invalid diagram")
    details = err.get("details") or {}
    if details.get("line"):
        msg += f" (line {details['line']}, column {details.get('column', '?')})"
    return False, result.get("diagramType"), msg


def render(key, code, fmt):
    """Returns (ok, output_bytes_or_error, headers). Costs 5 credits."""
    status, headers, raw = call(
        "POST", "/render", key, {"code": code, "format": fmt}
    )
    if status == 200:
        return True, raw, headers
    return False, error_text(raw), headers


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("files", nargs="*", help="Mermaid source files (.mmd)")
    parser.add_argument(
        "--format", choices=sorted(EXTENSIONS), default="svg",
        help="output format (default: svg)",
    )
    parser.add_argument(
        "--out", metavar="DIR",
        help="write outputs into DIR instead of next to each source file",
    )
    parser.add_argument(
        "--balance", action="store_true",
        help="print the API balance and endpoint costs, then exit (free)",
    )
    parser.add_argument(
        "--no-validate", action="store_true",
        help="skip the 1-credit validation and render directly "
        "(a failed render still costs the full render price)",
    )
    args = parser.parse_args()

    key = api_key()
    bal = get_balance(key)
    show_balance(bal)

    if args.balance:
        return
    if not args.files:
        sys.exit("No diagram files given. Pass .mmd files, or --balance.")

    per_file = COST_RENDER + (0 if args.no_validate else COST_VALIDATE)
    needed = per_file * len(args.files)
    if len(args.files) > 1:
        remaining = bal.get("remaining")
        if remaining is not None and remaining < needed:
            sys.exit(
                f"Batch of {len(args.files)} diagrams needs about {needed} "
                f"credits but only {remaining} remain. Nothing was rendered."
            )
        print(
            f"Batch: {len(args.files)} diagrams, about {needed} credits "
            f"(validate {COST_VALIDATE} + render {COST_RENDER} each)."
        )

    if args.out:
        os.makedirs(args.out, exist_ok=True)

    failures = 0
    for path in args.files:
        with open(path, encoding="utf-8") as fh:
            code = fh.read()
        stem = os.path.splitext(os.path.basename(path))[0]
        out_path = os.path.join(
            args.out or os.path.dirname(os.path.abspath(path)),
            stem + EXTENSIONS[args.format],
        )
        if not args.no_validate:
            valid, dtype, msg = validate(key, code)
            if not valid:
                failures += 1
                print(f"SKIP {path}: invalid diagram — {msg}")
                continue
            print(f"Valid {path} ({dtype or 'unknown type'}), rendering...")
        ok, result, headers = render(key, code, args.format)
        if not ok:
            failures += 1
            print(f"FAIL {path}: {result}")
            continue
        with open(out_path, "wb") as fh:
            fh.write(result)
        cache = headers.get("x-render-cache", "?")
        version = headers.get("x-mermaid-version", "?")
        print(f"Wrote {out_path} ({len(result)} bytes, mermaid {version}, cache {cache})")

    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
