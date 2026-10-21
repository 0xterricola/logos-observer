# Basecamp-managed Observer

## Implemented

The native Logos Observer module exposes:

- `startService()`
- `getServiceStatus()`
- `stopService()`

Observer Manager provides Start, Stop, and Refresh Status controls.

The managed service listens on `127.0.0.1:18446` and uses
`~/.local/state/logos-observer/basecamp` for persistent state.

The module manages its own child process. It does not manage or
terminate separately launched Observer instances.

## Development runtime configuration

The current implementation requires two environment variables
in the Basecamp process environment:

- `LOGOS_OBSERVER_PYTHON`: absolute path to a Python interpreter
  with the required dependencies, including `cryptography`.
- `LOGOS_OBSERVER_RUNTIME_DIR`: absolute path to the directory
  containing `v2_server.py` and its supporting modules.

The `.lgx` includes the Observer Python source but does not yet
bundle a standalone Python interpreter and its dependencies.

## Verified on macOS

- Native and UI portable package builds succeed.
- Managed Observer starts and stops through Basecamp.
- HTTPS `/health` responds with HTTP 200.
- TLS certificate fingerprint persists after Stop/Start.
- Standalone Observer on port 8444 remains independently healthy.
- Immediate process failure produces an error status.

## Current limitations

- Runtime configuration depends on development environment variables.
- The managed Observer listens on localhost only.
- Direct connections from Casberi on another device are not enabled.
- Startup reports process launch before independently verifying
  application-level HTTPS readiness.
- Unexpected failures require manual recovery or restart.
- Portable runtime support and cross-platform lifecycle behavior
  remain unfinished.

This is a development-stage service-management integration,
not a fully standalone Observer distribution.
