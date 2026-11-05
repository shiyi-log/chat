# Private Chat

Private Chat is a self-hosted messaging suite. This repository brings the server, Android and iOS apps, the desktop app for macOS, Windows, and Linux, and the project documentation into one Git history.

## Repository layout

- `server/`: Go and MTProto server.
- `clients/android/`: Android client.
- `clients/ios/`: iOS client.
- `clients/desktop/`: macOS, Windows, and Linux client.
- `docs/`: architecture, migration, release, and operations documentation.
- `tests/`: repository-level integration checks.

## Development status

The component histories are being combined from the five published Private Chat repositories. Cross-platform login, messaging, uploads, Chinese-first UI, complete Telegram-facing UI cleanup, reproducible CI/CD, and a production release are still being validated. A successful source import does not imply those release requirements are complete.

There is no standalone Web client in the current suite. The five client platforms are Android, iOS, macOS, Windows, and Linux.

## Local server

The server and its local dependencies are configured in `server/`. Start from that directory and follow its Chinese README. Do not commit `.env`, local database/object-storage data, signing material, or production credentials.

## Component licenses

Each component retains its own license and upstream notices. See the license files in `server/`, `clients/android/`, `clients/ios/`, `clients/desktop/`, and `docs/`. The root repository does not replace those component-specific terms.

