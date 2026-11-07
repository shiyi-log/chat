#!/usr/bin/env python3
"""Print the unique Chat simulator app produced by an Xcode/Bazel build."""

import argparse
import plistlib
import sys
from pathlib import Path


def resolve_simulator_app(products_path):
    products = Path(products_path)
    paths = (
        [products]
        if products.suffix == ".app"
        else [products / "Telegram.app", *products.glob("bazel-out/*/bin/Telegram/Telegram.app")]
    )
    candidates = sorted({path.resolve() for path in paths if path.is_dir()})
    if not candidates:
        raise ValueError(f"No simulator app found in {products}")
    if len(candidates) != 1:
        raise ValueError("Ambiguous simulator apps: " + ", ".join(map(str, candidates)))

    app = candidates[0]
    plist_path = app / "Info.plist"
    try:
        with plist_path.open("rb") as handle:
            metadata = plistlib.load(handle)
    except (OSError, plistlib.InvalidFileException, ValueError) as error:
        raise ValueError(f"Cannot read {plist_path}: {error}") from error
    if not isinstance(metadata, dict):
        raise ValueError(f"Invalid Info.plist dictionary: {plist_path}")
    if metadata.get("CFBundleIdentifier") != "com.privatechat.ios":
        raise ValueError(f"Unexpected bundle identifier in {plist_path}; expected com.privatechat.ios")
    platforms = metadata.get("CFBundleSupportedPlatforms", [])
    if (
        metadata.get("DTPlatformName") != "iphonesimulator"
        or not isinstance(platforms, list)
        or "iPhoneSimulator" not in platforms
    ):
        raise ValueError(f"Expected an iphonesimulator app in {plist_path}")
    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("products_path", help="Debug-iphonesimulator directory or explicit .app path")
    arguments = parser.parse_args()
    try:
        app = resolve_simulator_app(arguments.products_path)
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(app)
    return 0


if __name__ == "__main__":
    sys.exit(main())
