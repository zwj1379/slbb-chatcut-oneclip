#!/usr/bin/env python3
"""Bounded stdio MCP client for an already authorized official local ChatCut server."""
import argparse
import json
import os
from pathlib import Path
import queue
import re
import subprocess
import sys
import threading
import time

from run_state import gate

FORBIDDEN_GENERATORS = {"submit_video", "submit_image", "submit_music", "submit_sound", "submit_voice",
                        "submit_avatar_video", "submit_video_translation"}


def business_error(result):
    if not isinstance(result, dict):
        return None
    if result.get("isError") or result.get("success") is False:
        return "MCP tool reported failure"
    structured = result.get("structuredContent")
    if isinstance(structured, dict) and structured.get("success") is False:
        return "Structured tool result reported failure"
    for item in result.get("content", []):
        if not isinstance(item, dict) or item.get("type") != "text":
            continue
        text = item.get("text", "").strip()
        if re.match(r"^(?:ERROR\s*:|tool call error\b|net::ERR_|HTTP\s+(?:429|5\d\d)\b)", text, re.I):
            return "Tool text reported failure"
        try:
            parsed = json.loads(text)
        except (ValueError, TypeError):
            continue
        if isinstance(parsed, dict) and (parsed.get("success") is False or parsed.get("error")):
            return "JSON tool text reported failure"
    return None


class Client:
    def __init__(self, command, timeout=30):
        self.timeout = timeout
        self.proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.DEVNULL, text=True, bufsize=1, shell=False)
        self.messages = queue.Queue()
        self.seq = 0
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        try:
            for line in self.proc.stdout:
                try:
                    msg = json.loads(line)
                    if isinstance(msg, dict):
                        self.messages.put(msg)
                except ValueError:
                    continue
        finally:
            self.messages.put(None)

    def send(self, msg):
        self.proc.stdin.write(json.dumps(msg, ensure_ascii=False) + "\n")
        self.proc.stdin.flush()

    def request(self, method, params=None):
        self.seq += 1
        rid = self.seq
        self.send({"jsonrpc": "2.0", "id": rid, "method": method, "params": params or {}})
        deadline = time.monotonic()+self.timeout
        while True:
            remaining = deadline-time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Response timeout; read back before any retry")
            try:
                msg = self.messages.get(timeout=remaining)
            except queue.Empty:
                raise TimeoutError("Response timeout; read back before any retry") from None
            if msg is None:
                raise RuntimeError("MCP server closed stdout; outcome may be uncertain")
            if "method" in msg and "id" in msg:
                if msg["method"] == "ping":
                    self.send({"jsonrpc": "2.0", "id": msg["id"], "result": {}})
                else:
                    self.send({"jsonrpc": "2.0", "id": msg["id"], "error": {
                        "code": -32601, "message": "Interactive requests require the host; not auto-approved"}})
                continue
            if msg.get("id") != rid:
                continue
            if "error" in msg:
                raise RuntimeError("JSON-RPC error; read back before retry")
            return msg.get("result", {})

    def initialize(self):
        self.request("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                                    "clientInfo": {"name": "single-clip-local-helper", "version": "2.0.0"}})
        self.send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def tools(self):
        tools, cursor = [], None
        for _ in range(20):
            data = self.request("tools/list", {"cursor": cursor} if cursor else {})
            tools.extend(data.get("tools", []))
            cursor = data.get("nextCursor")
            if not cursor:
                return tools
        raise RuntimeError("Unexpected tool pagination limit")

    def close(self):
        try:
            self.proc.stdin.close()
        except OSError:
            pass
        self.proc.terminate()
        try:
            self.proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.proc.kill()  # Only the helper's own MCP child, never the editor.
            self.proc.wait(timeout=3)


def command_from(args):
    if args.command_json:
        command = json.loads(Path(args.command_json).read_text(encoding="utf-8"))
        if not isinstance(command, list) or not command or not all(isinstance(x, str) and x for x in command):
            raise ValueError("Command file must be a nonempty JSON string array")
        return command
    if sys.platform == "darwin":
        wrapper = Path.home() / "Library/Application Support/ChatCut/chatcut-mcp"
    elif sys.platform.startswith("win"):
        wrapper = Path(os.environ.get("APPDATA", str(Path.home()))) / "ChatCut/chatcut-mcp.exe"
    else:
        raise ValueError("Supply the confirmed official stdio command; no default for this platform")
    if not wrapper.is_file():
        raise ValueError("Official local wrapper missing; no installation attempted")
    return [str(wrapper)]


def check_calls(calls, args):
    if not isinstance(calls, list) or not calls:
        raise ValueError("Call plan must be a nonempty array")
    for call in calls:
        if not isinstance(call, dict) or not isinstance(call.get("name"), str) or not isinstance(call.get("arguments"), dict):
            raise ValueError("Each call needs name:string and arguments:object")
        name = call["name"]
        if name in FORBIDDEN_GENERATORS:
            raise ValueError("Media generation is outside this Skill's scope")
        if "export" not in name.lower():
            continue
        if args.preview_export:
            output = call["arguments"].get("outputPath", "")
            if not output or not Path(output).name.startswith("preview_"):
                raise ValueError("Preview exports require an explicit preview_* outputPath")
        elif args.state_dir and args.revision:
            data = json.loads((Path(args.state_dir) / "run-state.json").read_text(encoding="utf-8"))
            gate(data, args.revision)
        else:
            raise ValueError("Formal export requires --state-dir and --revision with current user approval")


def validate_args(call, tool):
    schema = tool.get("inputSchema", {})
    arguments = call["arguments"]
    missing = set(schema.get("required", []))-set(arguments)
    if missing:
        raise ValueError("Missing required tool arguments: " + ", ".join(sorted(missing)))
    if schema.get("additionalProperties") is False:
        extra = set(arguments)-set(schema.get("properties", {}))
        if extra:
            raise ValueError("Unknown tool arguments: " + ", ".join(sorted(extra)))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("mode", choices=("list-tools", "call", "batch"))
    ap.add_argument("--command-json")
    ap.add_argument("--timeout", type=float, default=30)
    ap.add_argument("--tool")
    ap.add_argument("--args-file")
    ap.add_argument("--calls-file")
    ap.add_argument("--state-dir")
    ap.add_argument("--revision")
    ap.add_argument("--preview-export", action="store_true")
    args = ap.parse_args()
    client = None
    completed = []
    try:
        if not 0 < args.timeout <= 60:
            raise ValueError("Request timeout must be in (0,60] seconds")
        calls = []
        if args.mode == "call":
            if not args.tool or not args.args_file:
                raise ValueError("call requires --tool and --args-file")
            calls = [{"name": args.tool, "arguments": json.loads(Path(args.args_file).read_text(encoding="utf-8"))}]
        elif args.mode == "batch":
            if not args.calls_file:
                raise ValueError("batch requires --calls-file")
            calls = json.loads(Path(args.calls_file).read_text(encoding="utf-8"))
        if calls:
            check_calls(calls, args)
        client = Client(command_from(args), timeout=args.timeout)
        client.initialize()
        tools = client.tools()
        if args.mode == "list-tools":
            print(json.dumps({"tools": tools}, ensure_ascii=False))
            return 0
        catalog = {t["name"]: t for t in tools}
        for call in calls:
            if call["name"] not in catalog:
                raise ValueError("Tool not exposed by this server: " + call["name"])
            validate_args(call, catalog[call["name"]])
        for call in calls:
            # Recheck approval before each actual export call.
            if "export" in call["name"].lower():
                check_calls([call], args)
            result = client.request("tools/call", {"name": call["name"], "arguments": call["arguments"]})
            record = {"name": call["name"], "result": result}
            completed.append(record)
            if business_error(result):
                print(json.dumps({"success": False, "completed": completed, "error": business_error(result),
                                  "note": "Stopped without retry; inspect actual target state"}, ensure_ascii=False))
                return 1
        print(json.dumps({"success": True, "completed": completed}, ensure_ascii=False))
        return 0
    except (OSError, ValueError, RuntimeError, TimeoutError) as exc:
        print(json.dumps({"success": False, "error": str(exc), "completed": completed,
                          "note": "No automatic retries; preceding writes may have applied"}, ensure_ascii=False))
        return 2
    finally:
        if client:
            client.close()


if __name__ == "__main__":
    sys.exit(main())
