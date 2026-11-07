#!/usr/bin/env python3
"""Assemble and validate same-run Chat preview release assets."""

import argparse
import hashlib
import json
import re
import shutil
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path


DESKTOP_PLATFORMS = {
    "linux": ".tar.gz",
    "macos": ".zip",
    "windows": ".zip",
}
SERVER_BINARIES = (
    "idgen",
    "status",
    "dfs",
    "media",
    "authsession",
    "biz",
    "msg",
    "sync",
    "bff",
    "session",
    "gnetway",
)


def digest(path):
    checksum = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            checksum.update(block)
    return checksum.hexdigest()


def require_file(path, description):
    if not path.is_file() or path.is_symlink() or path.stat().st_size == 0:
        raise ValueError(f"missing non-empty regular file for {description}: {path}")
    return path


def run_artifact(artifacts_dir, prefix, run_id, run_attempt):
    attempt_limit = int(run_attempt)
    candidates = {}
    run_prefix = f"{prefix}-{run_id}-"
    for path in artifacts_dir.iterdir():
        if not path.name.startswith(run_prefix) or not path.is_dir() or path.is_symlink():
            continue
        attempt = path.name[len(run_prefix) :]
        if not attempt.isdigit() or int(attempt) > attempt_limit:
            continue
        attempt_number = int(attempt)
        if attempt_number in candidates:
            raise ValueError(f"duplicate {prefix} artifact for workflow attempt {attempt_number}")
        candidates[attempt_number] = path

    if not candidates:
        raise ValueError(f"missing CI artifact for this workflow run: {prefix}-{run_id}-[attempt]")
    attempt_number = max(candidates)
    return candidates[attempt_number], str(attempt_number)


def validate_tar(path, description, required_members):
    try:
        with tarfile.open(path, "r:gz") as archive:
            members = {member.name: member for member in archive.getmembers() if member.isfile()}
    except (OSError, tarfile.TarError) as error:
        raise ValueError(f"invalid {description} TAR archive: {error}") from error

    missing = set(required_members) - members.keys()
    if missing:
        raise ValueError(f"{description} TAR archive is missing: {', '.join(sorted(missing))}")
    empty = [name for name in required_members if members[name].size == 0]
    if empty:
        raise ValueError(f"{description} TAR archive has empty files: {', '.join(empty)}")
    return members


def validate_zip(path, description, required_members=(), required_suffixes=()):
    try:
        with zipfile.ZipFile(path) as archive:
            bad_member = archive.testzip()
            names = set(archive.namelist())
    except (OSError, zipfile.BadZipFile) as error:
        raise ValueError(f"invalid {description} ZIP archive: {error}") from error

    if bad_member:
        raise ValueError(f"{description} ZIP archive has a corrupt member: {bad_member}")
    missing = set(required_members) - names
    if missing:
        raise ValueError(f"{description} ZIP archive is missing: {', '.join(sorted(missing))}")
    for suffix in required_suffixes:
        if not any(name.endswith(suffix) for name in names):
            raise ValueError(f"{description} ZIP archive is missing a member ending in {suffix}")
    return names


def copy_payload(source, destination, name, records, stage, source_attempt):
    require_file(source, name)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    records.append(
        {
            "name": name,
            "path": destination.relative_to(stage).as_posix(),
            "size_bytes": destination.stat().st_size,
            "sha256": digest(destination),
            "source_workflow_run_attempt": source_attempt,
        }
    )


def create_web_archive(source_dir, destination, records, stage, source_attempt):
    index = require_file(source_dir / "index.html", "Web preview index")
    files = []
    for path in sorted(source_dir.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"Web artifact contains a symbolic link: {path.relative_to(source_dir)}")
        if path.is_file():
            relative = path.relative_to(source_dir).as_posix()
            if relative.startswith("../"):
                raise ValueError(f"Web artifact path escapes its root: {relative}")
            files.append((path, relative))
    if index not in [path for path, _ in files]:
        raise ValueError("Web preview index is not a regular artifact file")

    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path, relative in files:
            archive.write(path, relative)
    validate_zip(destination, "Web preview", required_members=("index.html",))
    records.append(
        {
            "name": "web-preview",
            "path": destination.relative_to(stage).as_posix(),
            "size_bytes": destination.stat().st_size,
            "sha256": digest(destination),
            "source_workflow_run_attempt": source_attempt,
        }
    )


def validate_desktop_manifest(path, platform, revision):
    try:
        manifest = json.loads(require_file(path, f"{platform} desktop build manifest").read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid {platform} desktop build manifest: {error}") from error
    if not isinstance(manifest, dict):
        raise ValueError(f"invalid {platform} desktop build manifest: expected a JSON object")
    if manifest.get("platform") != platform or manifest.get("configuration") != "Debug":
        raise ValueError(f"desktop manifest does not describe a {platform} Debug build")
    if manifest.get("source_revision") != revision:
        raise ValueError(f"desktop manifest does not match source revision {revision}")
    signing = manifest.get("signing")
    if not isinstance(signing, dict) or not isinstance(signing.get("status"), str):
        raise ValueError(f"desktop manifest is missing the {platform} signing status")
    return manifest


def validate_desktop_payload(path, platform, manifest):
    if platform == "linux":
        members = validate_tar(path, "Linux desktop Debug", ("Chat", "build-manifest.json"))
        with tarfile.open(path, "r:gz") as archive:
            embedded = json.load(archive.extractfile(members["build-manifest.json"]))
    elif platform == "windows":
        validate_zip(path, "Windows desktop Debug", ("Chat.exe", "build-manifest.json"))
        with zipfile.ZipFile(path) as archive:
            embedded = json.load(archive.open("build-manifest.json"))
    else:
        validate_zip(
            path,
            "macOS desktop Debug",
            required_suffixes=("Chat.app/Contents/MacOS/Chat", "Chat.app/Contents/Info.plist"),
        )
        return

    if embedded != manifest:
        raise ValueError(f"{platform} desktop archive manifest does not match its sidecar")


def build_readme(tag, revision):
    return (
        f"# Chat {tag} 预览候选\n\n"
        f"源码提交：`{revision}`\n\n"
        "这些独立构建产物仅供审阅和本地测试，不是正式发行版本。请用 `SHA256SUMS` 校验下载文件。\n\n"
        "- Android 包为 `afatDebug` APK，使用开发调试签名，不可作为正式发行包。\n"
        "- iOS 模拟器包为未签名构建，不能安装到 iPhone 或 iPad。\n"
        "- macOS、Windows、Linux 包为 Desktop Debug 构建；签名状态记录在 `build-manifest.json`。\n"
        "- 服务端包只包含 Linux 服务程序，不包含生产配置、数据库或密钥。\n"
        "- Web 包是开发预览构建。\n"
        "- 当前没有短信服务；本地登录验证使用 localfile outbox，不代表真实短信登录可用。\n"
        "- 包内不含生产签名材料、短信凭据或生产配置。正式发行仍需完成签名、发行配置和端到端验证。\n"
    )


def prepare_bundle(artifacts_dir, stage, tag, revision, run_id, run_attempt):
    records = []
    server, server_attempt = run_artifact(artifacts_dir, "chat-server-linux-preview", run_id, run_attempt)
    server_archive = require_file(server / "chat-server-linux-preview.tar.gz", "Linux server preview")
    validate_tar(server_archive, "Linux server preview", SERVER_BINARIES)
    copy_payload(
        server_archive,
        stage / "chat-server-linux-preview.tar.gz",
        "server-linux-preview",
        records,
        stage,
        server_attempt,
    )

    web, web_attempt = run_artifact(artifacts_dir, "chat-web-preview", run_id, run_attempt)
    create_web_archive(web, stage / "chat-web-preview.zip", records, stage, web_attempt)

    android, android_attempt = run_artifact(artifacts_dir, "chat-android-afat-debug", run_id, run_attempt)
    android_apk = require_file(android / "app.apk", "Android afatDebug APK")
    validate_zip(android_apk, "Android afatDebug APK", ("AndroidManifest.xml", "classes.dex"))
    copy_payload(
        android_apk,
        stage / "chat-android-afat-debug.apk",
        "android-afat-debug",
        records,
        stage,
        android_attempt,
    )

    ios, ios_attempt = run_artifact(artifacts_dir, "chat-ios-simulator-debug", run_id, run_attempt)
    ios_app = require_file(ios / "Chat-iOS-Simulator.zip", "iOS simulator preview")
    validate_zip(ios_app, "iOS simulator preview", required_suffixes=(".app/Info.plist",))
    copy_payload(
        ios_app,
        stage / "chat-ios-simulator-debug.zip",
        "ios-simulator-debug",
        records,
        stage,
        ios_attempt,
    )

    desktop_builds = {}
    for platform, suffix in DESKTOP_PLATFORMS.items():
        artifact, artifact_attempt = run_artifact(
            artifacts_dir,
            f"chat-desktop-{platform}-debug",
            run_id,
            run_attempt,
        )
        package_name = f"chat-desktop-{platform}-debug-{run_id}-{artifact_attempt}{suffix}"
        package = require_file(artifact / package_name, f"{platform} desktop Debug package")
        sidecar = require_file(
            artifact / f"{package_name}.manifest.json",
            f"{platform} desktop package manifest",
        )
        manifest = validate_desktop_manifest(sidecar, platform, revision)
        validate_desktop_payload(package, platform, manifest)
        copy_payload(
            package,
            stage / package_name,
            f"desktop-{platform}-debug",
            records,
            stage,
            artifact_attempt,
        )
        desktop_builds[platform] = manifest

    (stage / "README.md").write_text(build_readme(tag, revision), encoding="utf-8")
    manifest = {
        "product": "Chat",
        "release_type": "unsigned-preview",
        "tag": tag,
        "source_revision": revision,
        "workflow_run_id": run_id,
        "workflow_run_attempt": run_attempt,
        "artifacts": records,
        "desktop_builds": desktop_builds,
    }
    (stage / "build-manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    checksums = []
    for path in sorted(stage.iterdir()):
        if path.is_file() and not path.is_symlink():
            checksums.append(f"{digest(path)}  {path.name}")
    (stage / "SHA256SUMS").write_text("\n".join(checksums) + "\n", encoding="utf-8")


def parse_args(argv):
    parser = argparse.ArgumentParser(description="Package same-run Chat preview artifacts.")
    parser.add_argument("--artifacts-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-attempt", required=True)
    args = parser.parse_args(argv)

    if not re.fullmatch(r"v[^/]+-preview\.[^/]+", args.tag):
        parser.error("tag must be a v*-preview.* preview tag")
    if not re.fullmatch(r"[0-9a-fA-F]{40,64}", args.revision):
        parser.error("revision must be a full Git object ID")
    if not args.run_id.isdigit() or not args.run_attempt.isdigit():
        parser.error("workflow run ID and attempt must be numeric")
    if not args.artifacts_dir.is_dir():
        parser.error("artifact directory does not exist")
    return args


def main(argv=None):
    args = parse_args(argv)
    args.artifacts_dir = args.artifacts_dir.resolve()
    args.output_dir = args.output_dir.resolve()
    if args.output_dir.exists():
        raise SystemExit("refusing to overwrite an existing candidate output directory")

    try:
        args.output_dir.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix="chat-candidate-release-",
            dir=args.output_dir.parent,
        ) as temporary:
            stage = Path(temporary) / "candidate"
            stage.mkdir()
            prepare_bundle(
                args.artifacts_dir,
                stage,
                args.tag,
                args.revision,
                args.run_id,
                args.run_attempt,
            )
            stage.rename(args.output_dir)
    except (OSError, ValueError, tarfile.TarError, zipfile.BadZipFile, json.JSONDecodeError) as error:
        raise SystemExit(str(error)) from error

    print(f"Packaged preview assets: {args.output_dir}")
    print(f"SHA256SUMS: {args.output_dir / 'SHA256SUMS'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
