#!/usr/bin/env python3
"""Read-only Desktop preflight. Static success is NOT an MCP health check."""
import argparse
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys


def app_paths(home, platform):
    if platform == "darwin":
        return [Path("/Applications/ChatCut.app"), home / "Applications/ChatCut.app"]
    if platform.startswith("win"):
        roots = [Path(os.environ.get("LOCALAPPDATA", str(home))) / "Programs",
                 Path(os.environ.get("LOCALAPPDATA", str(home))),
                 Path(os.environ.get("PROGRAMFILES", "C:/Program Files"))]
        return [p / "ChatCut/ChatCut.exe" for p in roots]
    return []


def running(platform):
    command = (["pgrep", "-f", "ChatCut.app/Contents/MacOS/ChatCut"]
               if platform == "darwin" else ["tasklist", "/FI", "IMAGENAME eq ChatCut.exe", "/FO", "CSV"])
    try:
        r = subprocess.run(command, capture_output=True, text=True, timeout=5)
        return r.returncode == 0 and (platform == "darwin" or "chatcut.exe" in r.stdout.lower())
    except (OSError, subprocess.TimeoutExpired):
        return False


def inspect(home, platform):
    report = {"check_type": "static_only", "session_connection_verified": False,
              "static_checks_passed": False, "missing": [], "warnings": [], "local_servers": []}
    if platform != "darwin" and not platform.startswith("win"):
        report["missing"].append("unsupported_platform")
        return report, 5
    app = next((p for p in app_paths(home, platform) if p.exists()), None)
    report["app_found"] = app is not None
    if app:
        report["app_path"] = str(app)
        if platform == "darwin":
            try:
                with (app / "Contents/Info.plist").open("rb") as f:
                    report["desktop_version"] = plistlib.load(f).get("CFBundleShortVersionString")
            except (OSError, ValueError, plistlib.InvalidFileException):
                report["warnings"].append("version_unreadable")
    else:
        report["missing"].append("desktop_app")
    report["app_running"] = running(platform)
    if not report["app_running"]:
        report["missing"].append("desktop_process")
    config = home / ".workbuddy/mcp.json"
    report["workbuddy_config_present"] = config.is_file()
    servers = {}
    bad_config = False
    if config.is_file():
        try:
            data = json.loads(config.read_text(encoding="utf-8"))
            servers = data.get("mcpServers", {})
            if not isinstance(servers, dict):
                raise ValueError("invalid servers")
        except (OSError, ValueError, AttributeError):
            bad_config = True
            servers = {}
            report["warnings"].append("config_unreadable_or_invalid_no_rewrite")
    for name, entry in servers.items():
        if "chatcut" not in name.lower() or not isinstance(entry, dict):
            continue
        if entry.get("disabled"):
            continue
        command = entry.get("command")
        if not isinstance(command, str):
            continue  # HTTP entries do not prove a Desktop connection.
        path = Path(command).expanduser()
        resolved = str(path) if path.is_file() else shutil.which(command)
        valid = bool(resolved and Path(resolved).is_file()
                     and (platform.startswith("win") or os.access(resolved, os.X_OK)))
        report["local_servers"].append({"name": name, "command_executable": valid})
    wrapper = (home / "Library/Application Support/ChatCut/chatcut-mcp" if platform == "darwin"
               else Path(os.environ.get("APPDATA", str(home))) / "ChatCut/chatcut-mcp.exe")
    report["official_wrapper_present"] = wrapper.is_file()
    if not any(x["command_executable"] for x in report["local_servers"]):
        report["warnings"].append("no_valid_workbuddy_local_entry_use_current_session_tools_or_allowed_official_wrapper")
    report["ffprobe_available"] = bool(shutil.which("ffprobe"))
    report["ffmpeg_available"] = bool(shutil.which("ffmpeg"))
    if not report["ffprobe_available"] or not report["ffmpeg_available"]:
        report["missing"].append("export_validation_tools")
    report["warnings"].append("verify_actual_MCP_and_open_project_in_current_session")
    code = 2 if not app else 3 if not report["app_running"] else 6 if report["missing"] else 7 if bad_config else 0
    report["static_checks_passed"] = code == 0
    return report, code


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="Compatibility flag; all modes are read-only")
    args = ap.parse_args()
    report, code = inspect(Path.home(), sys.platform)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main())
