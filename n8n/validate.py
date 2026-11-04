"""Static checks for the n8n workflow export (stdlib only, used in CI).

Usage: python n8n/validate.py [path/to/workflow.json]
Exits non-zero with one line per problem.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

DEFAULT_PATH = Path(__file__).parent / "workflows" / "triage.json"
DECISIONS = ("auto_send", "human_review", "escalate")
REQUIRED_TYPES = {
    "n8n-nodes-base.webhook",
    "n8n-nodes-base.httpRequest",
    "n8n-nodes-base.switch",
    "n8n-nodes-base.set",
    "n8n-nodes-base.slack",
    "n8n-nodes-base.emailSend",
    "n8n-nodes-base.respondToWebhook",
}
# Nodes that talk to third parties must ship disabled with placeholder credentials.
NOTIFIER_TYPES = {"n8n-nodes-base.slack", "n8n-nodes-base.emailSend", "n8n-nodes-base.emailReadImap"}


def _children(connections: dict, name: str) -> list[list[str]]:
    outputs = connections.get(name, {}).get("main", [])
    return [[c["node"] for c in out or []] for out in outputs]


def _reachable(connections: dict, start: str) -> set[str]:
    seen, stack = set(), [start]
    while stack:
        n = stack.pop()
        if n in seen:
            continue
        seen.add(n)
        stack.extend(c for out in _children(connections, n) for c in out)
    return seen


def validate(wf: dict) -> list[str]:
    errors: list[str] = []
    nodes = wf.get("nodes")
    connections = wf.get("connections")
    if not isinstance(nodes, list) or not isinstance(connections, dict):
        return ["workflow must have a 'nodes' list and a 'connections' object"]
    if not wf.get("id") or not wf.get("name"):
        errors.append("workflow needs a fixed 'id' (import.sh publishes by id) and a 'name'")

    by_name = {n["name"]: n for n in nodes}
    dupes = [k for k, v in Counter(n["name"] for n in nodes).items() if v > 1]
    if dupes:
        errors.append(f"duplicate node names: {dupes}")
    missing = REQUIRED_TYPES - {n["type"] for n in nodes}
    if missing:
        errors.append(f"missing node types: {sorted(missing)}")

    for src, kinds in connections.items():
        if src not in by_name:
            errors.append(f"connection from unknown node {src!r}")
        for out in kinds.get("main", []):
            for c in out or []:
                if c["node"] not in by_name:
                    errors.append(f"connection {src!r} -> unknown node {c['node']!r}")

    hooks = [n for n in nodes if n["type"] == "n8n-nodes-base.webhook"]
    for h in hooks:
        p = h["parameters"]
        if p.get("httpMethod") != "POST" or p.get("path") != "ticket":
            errors.append(f"webhook {h['name']!r} must be POST /ticket")
        if p.get("responseMode") != "responseNode":
            errors.append(f"webhook {h['name']!r} must use responseMode=responseNode")
        if h.get("disabled"):
            errors.append(f"webhook {h['name']!r} must be enabled")

    for n in nodes:
        if n["type"] in NOTIFIER_TYPES:
            if not n.get("disabled"):
                errors.append(f"{n['name']!r} must ship disabled")
            for cred in (n.get("credentials") or {}).values():
                if not str(cred.get("id", "")).startswith("REPLACE_WITH_"):
                    errors.append(f"{n['name']!r} must use a placeholder credential id")
        if n["type"] == "n8n-nodes-base.httpRequest" and "/tickets" not in str(n["parameters"].get("url", "")):
            errors.append(f"{n['name']!r} does not call the triage API")

    if not any(
        n["type"] == "n8n-nodes-base.httpRequest"
        and n["parameters"].get("method") == "POST"
        and str(n["parameters"].get("url", "")).endswith("/tickets")
        for n in nodes
    ):
        errors.append("no HTTP Request node POSTs to .../tickets")

    switches = [n for n in nodes if n["type"] == "n8n-nodes-base.switch"]
    if len(switches) != 1:
        errors.append(f"expected exactly one Switch node, found {len(switches)}")
    else:
        sw = switches[0]
        rules = sw["parameters"].get("rules", {}).get("values", [])
        keys = [r.get("outputKey") for r in rules]
        values = [c.get("rightValue") for r in rules for c in r["conditions"]["conditions"]]
        if keys != list(DECISIONS) or values != list(DECISIONS):
            errors.append(f"switch outputs must be {list(DECISIONS)}, got keys={keys} values={values}")
        outs = _children(connections, sw["name"])
        for i, decision in enumerate(DECISIONS):
            branch = set().union(*(_reachable(connections, c) for c in outs[i])) if i < len(outs) else set()
            branch_nodes = [by_name[b] for b in branch if b in by_name]
            types = {n["type"] for n in branch_nodes}
            enabled_sets = [n for n in branch_nodes if n["type"] == "n8n-nodes-base.set" and not n.get("disabled")]
            for need in ("n8n-nodes-base.slack", "n8n-nodes-base.emailSend", "n8n-nodes-base.respondToWebhook"):
                if need not in types:
                    errors.append(f"{decision} branch has no {need.split('.')[-1]} node")
            if not enabled_sets:
                errors.append(f"{decision} branch has no enabled Set (summary) node")

    # Every webhook run must end in a response: the main path and the API error path.
    for h in hooks:
        responders = [
            b
            for b in _reachable(connections, h["name"])
            if by_name.get(b, {}).get("type") == "n8n-nodes-base.respondToWebhook"
        ]
        if len(responders) < 2:
            errors.append("expected a Respond to Webhook node on both the success and the API-error path")
    return errors


def main(argv: list[str]) -> int:
    path = Path(argv[1]) if len(argv) > 1 else DEFAULT_PATH
    try:
        wf = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"{path}: cannot load workflow: {exc}")
        return 1
    errors = validate(wf)
    for e in errors:
        print(f"{path}: {e}")
    if not errors:
        types = Counter(n["type"].split(".")[-1] for n in wf["nodes"])
        print(f"{path}: OK ({len(wf['nodes'])} nodes: {dict(sorted(types.items()))})")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
