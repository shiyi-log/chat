#!/usr/bin/env python3
"""Verify that a clean Android install opens in Simplified Chinese."""

import argparse
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path


EXPECTED_LABEL = "开始聊天"
ENGLISH_FALLBACK = "Start Messaging"


def has_expected_label(hierarchy):
    try:
        root = ET.fromstring(hierarchy)
    except ET.ParseError:
        return False

    labels = []
    for node in root.iter():
        labels.extend((node.attrib.get("text", ""), node.attrib.get("content-desc", "")))
    return any(EXPECTED_LABEL in label for label in labels)


def report_hierarchy_result(hierarchy, stream=None):
    stream = stream or sys.stderr
    if has_expected_label(hierarchy):
        print("Verified Simplified Chinese first-launch label: 开始聊天")
        return True

    if ENGLISH_FALLBACK in hierarchy:
        print("Expected Simplified Chinese, but found the English fallback: Start Messaging", file=stream)
    else:
        print("Expected Simplified Chinese first-launch label: 开始聊天", file=stream)
    return False


def run_adb(adb, serial, *arguments, timeout=30):
    command = [adb]
    if serial:
        command.extend(("-s", serial))
    command.extend(arguments)
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"{' '.join(command)} failed: {detail}")
    return result.stdout


def wait_for_boot(adb, serial, timeout_seconds):
    deadline = time.monotonic() + timeout_seconds
    run_adb(adb, serial, "wait-for-device", timeout=timeout_seconds)
    while time.monotonic() < deadline:
        if run_adb(adb, serial, "shell", "getprop", "sys.boot_completed").strip() == "1":
            return
        time.sleep(2)
    raise RuntimeError("Android emulator did not finish booting before the timeout")


def run_emulator_smoke(args):
    apk = args.apk.resolve()
    if not apk.is_file():
        raise RuntimeError(f"Android APK does not exist: {apk}")

    adb = args.adb or shutil.which("adb")
    if not adb:
        raise RuntimeError("adb was not found; install Android platform-tools or pass --adb")

    wait_for_boot(adb, args.serial, args.timeout_seconds)
    run_adb(adb, args.serial, "install", "-r", str(apk), timeout=180)
    run_adb(adb, args.serial, "shell", "pm", "clear", args.package)
    run_adb(
        adb,
        args.serial,
        "shell",
        "am",
        "start",
        "-W",
        "-n",
        f"{args.package}/{args.activity}",
        timeout=60,
    )

    deadline = time.monotonic() + args.timeout_seconds
    hierarchy_path = "/sdcard/chat-first-launch-window.xml"
    while time.monotonic() < deadline:
        try:
            run_adb(adb, args.serial, "shell", "uiautomator", "dump", hierarchy_path, timeout=20)
            hierarchy = run_adb(adb, args.serial, "exec-out", "cat", hierarchy_path, timeout=20)
            if has_expected_label(hierarchy):
                return report_hierarchy_result(hierarchy)
        except (RuntimeError, subprocess.TimeoutExpired):
            pass
        time.sleep(2)

    report_hierarchy_result(hierarchy if "hierarchy" in locals() else "")
    raise RuntimeError("Android first-launch screen did not show the Simplified Chinese label before timeout")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-hierarchy", type=Path, help="check a saved uiautomator XML hierarchy")
    parser.add_argument("--apk", type=Path, help="APK to install on a booted emulator")
    parser.add_argument("--adb", help="adb executable; defaults to adb on PATH")
    parser.add_argument("--serial", default="emulator-5554", help="adb device serial")
    parser.add_argument("--package", default="com.privatechat.messenger.beta")
    parser.add_argument("--activity", default="org.telegram.ui.LaunchActivity")
    parser.add_argument("--timeout-seconds", type=int, default=180)
    args = parser.parse_args()

    try:
        if args.check_hierarchy:
            return 0 if report_hierarchy_result(args.check_hierarchy.read_text(encoding="utf-8")) else 1
        if not args.apk:
            parser.error("--apk is required unless --check-hierarchy is used")
        run_emulator_smoke(args)
        return 0
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
