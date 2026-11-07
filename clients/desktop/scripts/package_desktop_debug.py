#!/usr/bin/env python3
import argparse
import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path


def signature_status(platform, main_binary):
    if platform == "linux":
        return {"status": "not-applicable", "details": "No native signature check applies."}
    if platform == "macos":
        verification = subprocess.run(
            ["codesign", "--verify", "--deep", "--strict", str(main_binary)],
            capture_output=True,
            text=True,
        )
        display = subprocess.run(
            ["codesign", "-dv", "--verbose=4", str(main_binary)],
            capture_output=True,
            text=True,
        )
        details = (display.stdout + display.stderr).strip()
        verify_details = (verification.stdout + verification.stderr).strip()
        authority = next(
            (line.partition("=")[2] for line in details.splitlines() if line.startswith("Authority=")),
            None,
        )
        if "Signature=adhoc" in details:
            identity = "ad-hoc"
        else:
            identity = authority
        if verification.returncode == 0:
            status = "valid"
        elif "code object is not signed at all" in verify_details.lower():
            status = "unsigned"
        else:
            status = "invalid-or-unverifiable"
        return {
            "status": status,
            "identity": identity,
            "verification_exit_code": verification.returncode,
            "details": verify_details.replace(str(main_binary), main_binary.name)[:2000],
        }

    powershell = shutil.which("powershell.exe") or shutil.which("powershell")
    if not powershell:
        raise RuntimeError("PowerShell is required to inspect the Windows Authenticode status.")
    command = (
        "$signature = Get-AuthenticodeSignature -LiteralPath $env:CHAT_SIGNING_TARGET; "
        "$signer = if ($signature.SignerCertificate) { $signature.SignerCertificate.Subject } "
        "else { $null }; "
        "$json = @{ status = [string]$signature.Status; signer = $signer } | ConvertTo-Json -Compress; "
        "[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($json))"
    )
    environment = os.environ.copy()
    environment["CHAT_SIGNING_TARGET"] = str(main_binary)
    result = subprocess.run(
        [powershell, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", command],
        capture_output=True,
        text=True,
        env=environment,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "PowerShell signature inspection failed.")
    encoded = base64.b64decode(result.stdout.strip()).decode("utf-8")
    return json.loads(encoded)


def runtime_files(platform, build_dir):
    if platform == "linux":
        main_binary = build_dir / "Chat"
        candidates = [
            path
            for path in build_dir.iterdir()
            if path.is_file()
            and (path.name in {"Chat", "Updater", "Packer"} or ".so" in path.name)
        ]
    elif platform == "windows":
        main_binary = build_dir / "Chat.exe"
        candidates = [
            path
            for path in build_dir.iterdir()
            if path.is_file() and path.suffix.lower() in {".exe", ".dll", ".pdb"}
        ]
    else:
        main_binary = build_dir / "Chat.app"
        executable = main_binary / "Contents" / "MacOS" / "Chat"
        if not executable.is_file():
            raise FileNotFoundError(f"Debug application not found: {executable}")
        candidates = [main_binary]

    if not main_binary.is_file() and platform != "macos":
        raise FileNotFoundError(f"Debug application not found: {main_binary}")
    executable = main_binary / "Contents" / "MacOS" / "Chat" if platform == "macos" else main_binary
    if executable.stat().st_size == 0:
        raise RuntimeError(f"Debug application is empty: {executable}")
    if platform == "windows" and not any(path.name == "Chat.exe" for path in candidates):
        raise FileNotFoundError(f"Debug application not found: {main_binary}")
    return main_binary, sorted(candidates, key=lambda path: path.name)


def file_records(paths):
    records = []
    for path in paths:
        file_path = path / "Contents" / "MacOS" / "Chat" if path.is_dir() else path
        digest = hashlib.sha256()
        with file_path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        records.append({
            "file": file_path.relative_to(path.parent).as_posix(),
            "size_bytes": file_path.stat().st_size,
            "sha256": digest.hexdigest(),
        })
    return records


def write_manifest(path, platform, signature, files):
    manifest = {
        "product": "Chat Desktop",
        "platform": platform,
        "configuration": "Debug",
        "api_credentials": "Telegram API test-only credentials",
        "source_revision": os.environ.get("GITHUB_SHA"),
        "signature_modified_during_packaging": False,
        "signing": signature,
        "files": file_records(files),
    }
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def create_archive(platform, files, manifest_path, output):
    output.parent.mkdir(parents=True, exist_ok=True)
    if platform == "macos":
        subprocess.run(
            ["ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", str(files[0]), str(output)],
            check=True,
        )
        return

    if platform == "linux":
        with tarfile.open(output, "w:gz", compresslevel=1) as archive:
            for path in files:
                archive.add(path, arcname=path.name, recursive=False)
            archive.add(manifest_path, arcname="build-manifest.json")
        return

    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=1) as archive:
        for path in files:
            archive.write(path, arcname=path.name)
        archive.write(manifest_path, arcname="build-manifest.json")


def main():
    parser = argparse.ArgumentParser(description="Package a real Chat Desktop Debug build.")
    parser.add_argument("--platform", choices=("linux", "macos", "windows"), required=True)
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    build_dir = args.build_dir.resolve()
    output = args.output.resolve()
    manifest_path = Path(str(output) + ".manifest.json")
    if build_dir.name != "Debug":
        raise SystemExit("Only a Debug output directory can be packaged.")
    if not build_dir.is_dir():
        raise SystemExit(f"Debug output directory not found: {build_dir}")
    if output.exists() or manifest_path.exists():
        raise SystemExit(f"Refusing to overwrite an existing package: {output}")

    try:
        main_binary, files = runtime_files(args.platform, build_dir)
        signing = signature_status(args.platform, main_binary)
        with tempfile.TemporaryDirectory(prefix="chat-desktop-debug-") as temporary_directory:
            temporary_manifest = Path(temporary_directory) / "build-manifest.json"
            write_manifest(temporary_manifest, args.platform, signing, files)
            create_archive(args.platform, files, temporary_manifest, output)
            shutil.copyfile(temporary_manifest, manifest_path)
    except (FileNotFoundError, RuntimeError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error)) from error

    print(f"Packaged {args.platform} Debug build: {output}")
    print(f"Signature status: {signing['status']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
