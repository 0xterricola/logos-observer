# Observer

**Local-first observability for the Logos ecosystem.**

Observer provides CLI-first monitoring, diagnostics, and secure read-only access to Logos node data. It also integrates with Logos Basecamp for service management, setup diagnostics, device pairing, and access to selected Basecamp Chat data.

Observer runs alongside infrastructure you control, without requiring a centralized monitoring service.

## Overview

Observer has three complementary components:

| Component | Purpose |
| --- | --- |
| **Observer CLI and Runtime** | Logos node monitoring, network health, mining, consensus, and rewards diagnostics |
| **Observer API** | Sanitized, authenticated, read-only access for trusted clients |
| **Observer for Basecamp** | Service management, readiness checks, QR pairing, and Chat integration |

The standalone runtime works independently of Basecamp.

Basecamp is an additional interface, not the foundation of Observer's monitoring capabilities.

## Design Principles

- **CLI-first:** Operational capabilities should remain accessible without a graphical interface.
- **Interface-agnostic:** CLI, API, and graphical interfaces should share underlying functionality.
- **Local-first:** Infrastructure and monitoring data remain under the operator's control.
- **Read-only client access:** Only explicitly implemented and authorized read operations are exposed.
- **Least privilege:** Paired devices receive individually scoped credentials.
- **No generic proxying:** Clients never receive unrestricted access to upstream Logos APIs.

## Features

### Node Monitoring

Observer provides monitoring and diagnostics for Logos nodes, including:

- Node health and reachability
- Synchronization status and block height
- Chain-tip information
- Network connectivity and peers
- Mining status and reward eligibility
- Mining balances and eligible-note aggregates
- Rewards and expiration telemetry
- Sanitized operational status for external clients

Node-facing monitoring is available independently of Basecamp.

Some extended mining, rewards, and consensus telemetry uses an optional local collector that produces sanitized snapshots.

### Observer for Basecamp

Observer includes two Basecamp modules:

| Module | ID | Purpose |
| --- | --- | --- |
| Observer Core | `observer` | Managed service, health checks, and pairing operations |
| Observer UI | `observer_ui` | Graphical setup, device pairing, and diagnostics |

The current Basecamp interface includes:

- Managed Observer start and stop controls
- Six-check Setup Readiness dashboard
- Guided recovery actions
- LAN and HTTPS diagnostics
- QR-based device pairing
- Authorized-device status
- Basecamp Chat availability checks
- Collapsible advanced settings
- Service health and technical diagnostics

The Basecamp UI does not yet expose every standalone node-monitoring capability.

A future milestone will bring existing monitoring functionality into Basecamp through shared APIs, while preserving CLI access.

### Secure Client Access

Observer v2 provides authenticated access for trusted devices using:

- TLS 1.3
- Persistent ECDSA P-256 server identity
- SHA-256 SPKI certificate pinning
- Five-minute, single-use QR pairing offers
- Per-device HMAC-SHA256 credentials
- Explicit authorization scopes
- Persistent nonce and replay protection
- Device revocation
- Sanitized and allowlisted responses

Basecamp Chat access requires the explicitly granted `chat.read` scope.

Observer has been exercised against live Logos node and Basecamp Chat runtimes, including QR pairing with a Casberi client.

## Architecture

```text
                  Trusted Client
                 (mobile / desktop)
                         |
              Pinned TLS 1.3 + HMAC
                         |
                         v
                      Observer
                         |
                Scoped Read API
                         |
              +----------+----------+
              |                     |
              v                     v
       Logos Node API       Basecamp JSON-RPC
        (localhost)          (localhost)
              |                     |
              v                     v
       Node / Network          Basecamp Chat
       Mining / Rewards
```

Observer deliberately exposes a narrower interface than its upstream services.

The raw Logos node API and Basecamp JSON-RPC bridge should remain bound to loopback.

External clients are never granted arbitrary RPC forwarding, node control, wallet access, or private-key access.

## Getting Started

### Requirements

For standalone development:

- Python 3
- Dependencies listed in `requirements.txt`
- A locally accessible Logos node for node-monitoring functionality

Basecamp integration additionally requires Logos Basecamp and the relevant module-building tools.

### Clone the Repository

```bash
git clone https://github.com/0xterricola/observer.git
cd observer
```

### Install Python Dependencies

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
```

### Start Observer v2

Replace the example LAN address with your own:

```bash
LAN_IP=192.168.1.20

./.venv/bin/python v2_server.py \
  --host "$LAN_IP" \
  --advertise-host "$LAN_IP" \
  --port 8081 \
  --state-dir .v2-state \
  --upstream http://127.0.0.1:8080
```

Keep the underlying Logos node API on localhost.

Restrict access to the Observer listener to trusted devices and networks.

### Pair a Trusted Device

From another terminal:

```bash
LAN_IP=192.168.1.20

./.venv/bin/python v2_pair_cli.py \
  --state-dir .v2-state \
  --host "$LAN_IP" \
  --port 8081 \
  --name "Observer"
```

The pairing offer expires after five minutes.

Never publish live pairing secrets, device credentials, or private TLS keys.

The portable packaged runtime also provides an `observer` executable with pairing functionality.

## Basecamp Integration

### Build Observer Core

```bash
nix build -L \
  './integrations/basecamp#lgx-portable' \
  --out-link result-core
```

### Build Observer UI

```bash
nix build -L \
  './integrations/basecamp-ui#lgx-portable' \
  --out-link result-ui
```

For macOS ARM64, the portable Core packaging script additionally repairs platform dependencies and performs integrity and runtime checks:

```bash
./integrations/basecamp/scripts/package-portable-macos.sh \
  /tmp/observer-core.lgx
```

These commands produce development packages.

A Basecamp package catalogue, release signing, and automatic update discovery are being prepared.

Core and UI are intended to be independently versioned.

## Observer API

Observer v2 exposes narrowly scoped, authenticated read operations:

| Endpoint | Purpose | Required scope |
| --- | --- | --- |
| `GET /v2/status` | Combined authorized status | Granted sections |
| `GET /v2/network` | Network telemetry | `network.status.read` |
| `GET /v2/mining` | Mining telemetry | `mining.status.read` |
| `GET /v2/rewards` | Rewards telemetry | `rewards.status.read` |
| `GET /v2/chat/conversations` | Conversation metadata | `chat.read` |
| `GET /v2/chat/messages` | Message history | `chat.read` |

Pairing and device revocation use separate, authenticated lifecycle operations.

Observer does not provide arbitrary node RPC, transaction submission, mining control, or wallet-key access.

The `chat.read` scope may expose message content to an authorized client. Read-only access does not imply that data is nonsensitive.

## Security and Privacy

Observer is designed around explicit trust boundaries:

- No centralized application backend
- No global shared API credential
- No mandatory cloud relay
- No custody of node or wallet keys
- No arbitrary localhost or JSON-RPC proxy
- No implicit Basecamp Chat authorization
- No remote node-control endpoints

Each installation manages its own device credentials and persistent replay-protection state.

Operators should protect the TLS private key, device database, and network exposure of the Observer service.

Observer should not be exposed directly to the public Internet without an appropriate security and deployment review.

## Compatibility

Observer v2 is the current reference protocol.

The original v1 implementation remains available for reference and compatibility.

Some historical identifiers are intentionally preserved:

- `LOGOS-OBSERVER-V2`
- `logos-observer-v1`
- `logos-observer://pair`
- `_logos-observer._tcp`
- Existing persistent state-directory names

These are protocol or migration identifiers, not the current product name.

Previous Basecamp module IDs (`logos_observer` and `logos_observer_ui`) are distinct from the new IDs (`observer` and `observer_ui`).

Existing installations require an explicit module migration. Preserving device credentials and cryptographic identity is necessary for pairing continuity.

## Project Structure

| Path | Description |
| --- | --- |
| `observer.py` | Original v1 reference implementation |
| `v2_server.py` | v2 HTTPS server |
| `v2_pair_cli.py` | v2 device pairing CLI |
| `v2_node.py` | Sanitized node data mapping |
| `v2_rewards_collector.py` | Optional mining and consensus telemetry collector |
| `integrations/basecamp/` | Observer Core Basecamp module |
| `integrations/basecamp-ui/` | Observer graphical Basecamp module |
| `tests/` | Protocol and integration tests |
| `vectors/` | Cryptographic interoperability vectors |
| `docs/` | Technical and integration documentation |

## Development Status

Implemented and exercised:

- Standalone v1 and v2 reference implementations
- Node, network, mining, and rewards read routes
- TLS and scoped HMAC authentication
- Replay protection and device revocation
- Basecamp Chat read integration
- Basecamp-managed Observer service
- QR pairing and authorized-device reporting
- Six-check readiness dashboard
- Portable macOS and Linux packaging workflows

Current priorities:

- Complete the repository-wide rename and migration testing
- Publish Basecamp packages and a package catalogue
- Configure release signing and update discovery
- Improve first-run module initialization
- Bring CLI node-monitoring capabilities into Basecamp
- Expand cross-platform and client interoperability testing

## Technical Documentation

The detailed original protocol documentation has been preserved in:

[Historical Protocol Reference](docs/PROTOCOL_REFERENCE.md)

It includes v1 and v2 protocol specifications, pairing formats, HMAC canonicalization, authentication, replay protection, security boundaries, and reference examples.

Some historical deployment instructions may be outdated.

## License

No license has been selected yet.
