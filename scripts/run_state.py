#!/usr/bin/env python3
"""Local workflow log and preview-version gate; never edits or exports media."""
import argparse
import datetime
import json
from pathlib import Path
import sys
import time

STAGES = ("preflight", "ingest", "aroll", "visuals", "captions", "audio", "qa", "preview", "export")


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def save(path, data):
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def gate(data, revision):
    if data.get("status") != "approved":
        raise ValueError("Formal export requires explicit approval of the current preview")
    if data.get("approved_revision") != revision or data.get("preview", {}).get("revision") != revision:
        raise ValueError("Revision differs from the approved preview")


def summary(data):
    durations = {}
    for stage in data.get("stages", []):
        if "elapsed_seconds" in stage:
            durations[stage["name"]] = durations.get(stage["name"], 0) + stage["elapsed_seconds"]
    events = data.get("events", [])
    return {"status": data["status"], "stage_seconds": durations,
            "recorded_calls": sum(e["kind"] == "call" for e in events),
            "errors": sum(e["kind"] == "error" for e in events),
            "repairs": sum(e["kind"] == "repair" for e in events),
            "time_to_preview_seconds": data.get("preview", {}).get("time_to_preview_seconds"),
            "approval_wait_seconds": data.get("approval_wait_seconds"),
            "note": "Recorded calls only; not an automatic capture of all MCP calls"}


def operate(args):
    root = Path(args.dir).expanduser()
    path = root / "run-state.json"
    if args.action == "init":
        if path.exists():
            raise ValueError("State already exists; resume it rather than overwrite")
        root.mkdir(parents=True, exist_ok=True)
        data = {"schema_version": 1, "status": "running", "created_at": now(), "started_epoch": time.time(),
                "stages": [], "events": [], "preview_history": [], "edit_generation": 0}
        save(path, data)
        return summary(data)
    data = json.loads(path.read_text(encoding="utf-8"))
    action = args.action
    if action in ("summary", "gate"):
        if action == "gate":
            gate(data, args.revision)
        return summary(data)
    if data["status"] in ("blocked", "completed"):
        raise ValueError("Run is stopped; resolve scope with the user before a separate resumed run")
    if action == "start":
        if args.stage == "export":
            gate(data, args.revision)
        if any("end_at" not in s for s in data["stages"]):
            raise ValueError("End the current timed stage before starting another")
        if data["status"] == "awaiting_review":
            raise ValueError("Waiting for user review; record dirty before editing")
        if data["status"] == "approved" and args.stage != "export":
            raise ValueError("Record dirty before changing approved content")
        data["stages"].append({"name": args.stage, "start_at": now(), "start_epoch": time.time()})
    elif action == "end":
        current = next((s for s in reversed(data["stages"]) if "end_at" not in s), None)
        if current is None or current["name"] != args.stage:
            raise ValueError("No matching running stage")
        current.update(end_at=now(), elapsed_seconds=round(time.time()-current["start_epoch"], 3))
    elif action == "event":
        if args.kind in ("error", "repair") and not args.key:
            raise ValueError("Errors/repairs need a stable root-cause key")
        if args.kind == "repair" and any(e["kind"] == "repair" and e.get("key") == args.key for e in data["events"]):
            data["status"] = "blocked"
            data["blocked_reason"] = "Repair budget exhausted: " + args.key
            save(path, data)
            raise ValueError(data["blocked_reason"])
        data["events"].append({"at": now(), "stage": args.stage, "kind": args.kind,
                               "key": args.key, "detail": args.detail})
    elif action == "preview":
        if any("end_at" not in s for s in data["stages"]):
            raise ValueError("End timed stages before recording a review-ready preview")
        if not args.revision.strip() or not args.locator.strip():
            raise ValueError("A real version and a preview locator are required")
        data["preview"] = {"revision": args.revision, "locator": args.locator,
                           "generation": data["edit_generation"], "ready_at": now(), "ready_epoch": time.time(),
                           "time_to_preview_seconds": round(time.time()-data["started_epoch"], 3)}
        data["status"] = "awaiting_review"
        data.pop("approved_revision", None)
    elif action == "approve":
        p = data.get("preview", {})
        if data["status"] != "awaiting_review" or p.get("revision") != args.revision or p.get("generation") != data["edit_generation"]:
            raise ValueError("No unchanged preview with this revision awaiting review")
        if not args.message.strip():
            raise ValueError("Record the user's actual explicit confirmation; do not invent one")
        data.update(status="approved", approved_revision=args.revision, approved_at=now(),
                    confirmation=args.message, approval_wait_seconds=round(time.time()-p["ready_epoch"], 3))
    elif action == "dirty":
        if data.get("preview"):
            data["preview_history"].append(data.pop("preview"))
        data["edit_generation"] += 1
        data["status"] = "running"
        for k in ("approved_revision", "approved_at", "confirmation", "approval_wait_seconds"):
            data.pop(k, None)
    elif action == "block":
        data.update(status="blocked", blocked_reason=args.reason, blocked_at=now())
    elif action == "finish":
        gate(data, args.revision)
        if any("end_at" not in s for s in data["stages"]):
            raise ValueError("End export stage before finish")
        out = Path(args.output).expanduser().resolve()
        if not out.is_file() or out.stat().st_size == 0:
            raise ValueError("Nonempty delivery file missing")
        data.update(status="completed", output=str(out), finished_at=now())
    save(path, data)
    return summary(data)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="action", required=True)
    for action in ("init", "start", "end", "event", "preview", "approve", "dirty", "gate", "block", "finish", "summary"):
        p = sub.add_parser(action)
        p.add_argument("--dir", required=True)
        if action in ("start", "end", "event"):
            p.add_argument("--stage", choices=STAGES, required=True)
        if action in ("start", "preview", "approve", "gate", "finish"):
            p.add_argument("--revision", required=action != "start", default="")
        if action == "event":
            p.add_argument("--kind", choices=("call", "error", "repair", "note"), required=True)
            p.add_argument("--key", default="")
            p.add_argument("--detail", default="")
        if action == "preview":
            p.add_argument("--locator", required=True)
        if action == "approve":
            p.add_argument("--message", required=True)
        if action == "block":
            p.add_argument("--reason", required=True)
        if action == "finish":
            p.add_argument("--output", required=True)
    try:
        print(json.dumps(operate(ap.parse_args()), ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
