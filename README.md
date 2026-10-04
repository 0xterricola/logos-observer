# Logos Observer

A local-first, read-only sidecar for securely exposing a limited view of a Logos node to trusted client applications without exposing the raw Logos API.

The first integration target is a read-only client that connects directly to a user's own Logos node.

Observer currently contains the original v1 reference protocol and the newer v2 protocol designed for clients such as Casberi.

## Goal

The architecture is intentionally simple:

```text
iPhone / client
       │
       │ authenticated requests
       │ encrypted responses
       ▼
Logos Observer
       │
       │ localhost only
       ▼
Logos node API
127.0.0.1:8080
```

The raw Logos API stays bound to localhost.

The client never receives arbitrary access to the Logos API.

Observer exposes only explicitly implemented, sanitized, read-only endpoints.

There is:

- no centralized backend
- no shared/global API key
- no account system
- no OAuth session
- no cloud relay
- no arbitrary RPC proxy
- no custody of wallet or node keys

Each Observer installation manages its own paired devices.

## Current Status

Observer v1 remains implemented and available as the original reference protocol.

Observer v2 is now implemented in the repository and has been exercised end-to-end against a live Logos node across two physical machines.

The v2 reference implementation currently includes:

- TLS 1.3 only
- persistent self-signed ECDSA P-256 server identity
- SHA-256 SPKI pinning
- one-time five-minute QR/bootstrap pairing
- five-failure bootstrap invalidation
- scoped per-device credentials
- direct 256-bit HMAC-SHA256 device keys
- exact request-target signing
- ±120 second request timestamp validation
- persistent SQLite nonce/replay protection
- replay rejection across process restarts
- per-device revocation and self-revocation
- sanitized combined node status
- explicit network, mining, and rewards read routes
- omission of ungranted status sections
- `null` for granted sections whose upstream read fails
- explicit node-unreachable semantics
- full lowercase 64-character block-tip identifiers
- voucher counts without exposing voucher commitments or nullifiers
- interoperability vectors for HMAC, SPKI pinning, certificate parsing, and pairing QR format

The current test suite contains 47 tests covering protocol, TLS, pairing, HMAC authentication, replay protection, node mapping, status semantics, dedicated routes, revocation, and integration behavior.

The reference implementation has also been validated live with:

```text
Mac client
    │
    │ TLS 1.3 + SPKI pin
    ▼
Logos Observer v2
192.168.x.x
    │
    │ localhost-only read access
    ▼
Logos node API
127.0.0.1:8080
```

The live test demonstrated:

```text
pair
  ↓
receive scoped device credential
  ↓
signed GET /v2/status
  ↓
live sanitized Logos node data
  ↓
replay same nonce
  ↓
401 replay
  ↓
DELETE /v2/device
  ↓
401 revoked on subsequent use
```

Casberi interoperability is the next client-side integration step.

## Observer v2

Observer v2 replaces the v1 application-encrypted response envelope with pinned TLS 1.3 while retaining explicit request authentication and persistent replay protection.

The raw Logos API remains localhost-only.

Observer still does not provide arbitrary forwarding or arbitrary RPC access.

### v2 Network Architecture

Normal v2 deployment:

```text
                     trusted LAN

client ─────────────────────────────► Logos Observer v2
                                      192.168.x.x:8081
                                             │
                                             │ HTTP on loopback only
                                             ▼
                                      Logos node API
                                      127.0.0.1:8080
```

Port `8081` is the v2 default.

During migration, v1 and v2 can run side by side by explicitly assigning v2 a staging port such as `8443`:

```text
127.0.0.1:8080       raw Logos node API
192.168.x.x:8081     Observer v1
192.168.x.x:8443     Observer v2 staging
```

The staging port is not part of the v2 protocol contract.

### TLS Identity and SPKI Pinning

Observer v2 uses:

```text
TLS version:       TLS 1.3 only
server key:        ECDSA P-256
certificate:       self-signed
pin digest:        SHA-256
pin input:         DER SubjectPublicKeyInfo
pin encoding:      RFC 4648 base64url without padding
```

Pin format:

```text
sha256/<base64url SHA-256 digest>
```

Example:

```text
sha256/b5b_xWoDK7EJ11lQXxjG0-VqRbq6LqcNFrMf7pYBC8o
```

The private P-256 identity key is persistent.

Certificates may be regenerated to update expiration or Subject Alternative Names while reusing the same private key.

Because the pin covers the public-key SPKI rather than the certificate bytes, normal certificate renewal can preserve the client-visible Observer identity.

Replacing the private key changes the SPKI pin and requires clients to pair again.

Clients must verify the expected SPKI pin before sending the temporary bootstrap secret.

There is no CA trust requirement for the self-signed Observer certificate.

### v2 Pairing Model

Pairing is initiated locally by the node operator.

The reference implementation provides:

```text
v2_pair_cli.py
```

It creates a five-minute pairing offer using the same persistent TLS identity as the server.

The pairing URI has this form:

```text
logos-observer://pair?v=2
  &exp=<Unix expiration>
  &h=<Observer host:port>
  &b=<optional Bonjour instance>
  &pin=sha256/<SPKI pin>
  &s=<base64url 32-byte bootstrap secret>
  &n=<display name>
  &sc=<comma-separated offered scopes>
```

The URI is intended to be displayed locally, for example as a terminal QR code.

Observer does not expose a network endpoint for retrieving pairing QR material.

The bootstrap secret:

- is 32 random bytes
- expires after five minutes
- is valid for one successful pairing
- is invalidated after five failed activation attempts
- is stored by Observer only as a SHA-256 hash
- is not the permanent device credential

A client may accept only a subset of the offered scopes.

Pair activation:

```text
POST /v2/pair
```

Example request:

```json
{
  "secret": "<temporary bootstrap secret>",
  "device_name": "Alex's iPhone",
  "scopes": [
    "node.status.read",
    "network.status.read"
  ]
}
```

Example response:

```json
{
  "device_id": "d_...",
  "hmac_key": "<base64url 32-byte key>",
  "granted_scopes": [
    "node.status.read",
    "network.status.read"
  ]
}
```

The permanent HMAC key is generated by Observer and returned only over the already pinned TLS channel.

The permanent HMAC key is not contained in the QR.

Clients should store that credential in device-local secure storage such as iOS Keychain.

### v2 Read Scopes

Current read scopes:

```text
node.status.read
network.status.read
mining.status.read
rewards.status.read
```

Reserved:

```text
blend.status.read
```

Reserved control scopes are not part of the current read-only implementation:

```text
mining.control
rewards.claim
node.control
```

Read and control capabilities should not be mixed into the same pairing.

### v2 Routes

Current reference routes:

| Method | Route | Authentication | Scope |
| --- | --- | --- | --- |
| `POST` | `/v2/pair` | bootstrap + pinned TLS | offered scope subset |
| `GET` | `/v2/status` | device HMAC | returns granted sections |
| `GET` | `/v2/network` | device HMAC | `network.status.read` |
| `GET` | `/v2/mining` | device HMAC | `mining.status.read` |
| `GET` | `/v2/rewards` | device HMAC | `rewards.status.read` |
| `DELETE` | `/v2/device` | device HMAC | self-revocation |
| `GET` | `/v2/blend` | reserved | not active |

Unknown paths and unsupported methods are not forwarded to the Logos node.

Observer is not an arbitrary localhost proxy.

### v2 Combined Status

`GET /v2/status` returns one snapshot containing only sections granted to the paired device.

Example:

```json
{
  "v": 2,
  "observed_at": "2026-10-04T02:17:37Z",
  "node": {
    "reachable": true,
    "phase": "Following",
    "height": 9847,
    "tip": "ada389bee67111df35e6c942df0b15f47cc3889ec955724831f283f6ca69b85d"
  },
  "network": {
    "peers": 461
  },
  "mining": {
    "is_mining": true,
    "rewards_enabled": true,
    "auto_claim": true
  },
  "rewards": {
    "claimable_tickets": 0,
    "slots_until_expiry": null,
    "vouchers": 0,
    "total_claimable": "0"
  }
}
```

Status rules:

- an ungranted section is omitted
- a granted section whose upstream read fails is `null`
- values are never silently converted to zero because a read failed
- `tip` is the full lowercase hexadecimal block identifier or `null`
- amount values exposed by v2 are decimal strings

When the node itself is unreachable and `node.status.read` is granted:

```json
{
  "node": {
    "reachable": false,
    "phase": null,
    "height": null,
    "tip": null
  }
}
```

Every other granted section in that combined snapshot is then `null`.

### v2 Dedicated Read Routes

Dedicated read routes return their sanitized section object directly.

For example:

```text
GET /v2/network
```

may return:

```json
{
  "peers": 461
}
```

A granted dedicated read that fails upstream returns JSON `null`.

A request without the required scope returns:

```json
{
  "error": "scope"
}
```

with HTTP `403`.

`/v2/blend` remains reserved until its client-facing schema is frozen.

### Rewards Privacy Boundary

The raw Logos reward APIs may contain data that must not leave Observer.

Observer v2 intentionally exposes only sanitized aggregate values such as:

```text
claimable ticket count
nearest slots-until-expiry value
voucher count
total claimable amount
```

Voucher objects themselves do not cross the Observer boundary.

In particular, Observer must not expose:

- voucher commitments
- voucher nullifiers
- secret voucher material
- raw reward objects
- wallet private material

For `slots_until_expiry`, the current node API returns an array.

Observer exposes the minimum value from that array, representing the nearest expiry, or `null` when the array is empty.

### v2 Request Authentication

Authenticated v2 requests use:

```text
X-Observer-Device
X-Observer-Timestamp
X-Observer-Nonce
X-Observer-Signature
```

Protocol identifier:

```text
LOGOS-OBSERVER-V2
```

Canonical request:

```text
LOGOS-OBSERVER-V2
<METHOD>
<exact request-target>
<Unix timestamp>
<base64url 16-byte nonce>
<device ID>
<lowercase hex SHA-256 of exact body bytes>
```

Fields are joined by exactly one LF byte.

There is no trailing LF.

The request-target is signed exactly as transmitted:

```text
/path
```

or:

```text
/path?query
```

Rules:

- preserve query ordering
- preserve percent encoding
- do not normalize the path
- do not append a trailing `?` when no query exists
- fragments are not valid request-target input

The signature is:

```text
base64url(
  HMAC-SHA256(
    device_hmac_key,
    canonical_request
  )
)
```

without Base64 padding.

Unlike v1, the v2 permanent request key is a directly generated random 32-byte HMAC key rather than an HKDF-derived request key.

### v2 Authentication Order

Observer validates authenticated requests in this order:

```text
device
  ↓
timestamp
  ↓
signature
  ↓
scope
  ↓
consume nonce
  ↓
read node data
```

This ordering prevents unauthorized requests from consuming valid nonces before signature and scope authorization succeeds.

### v2 Replay Protection

Current policy:

```text
request freshness: ±120 seconds
nonce retention:   5 minutes
nonce size:        16 random bytes
nonce encoding:    base64url without padding
```

Used nonces are stored persistently in SQLite.

Replay protection therefore survives Observer process restarts.

Reusing a previously consumed nonce returns:

```json
{
  "error": "replay"
}
```

### v2 Errors

Current authentication/authorization errors:

| HTTP | Error | Meaning |
| --- | --- | --- |
| `401` | `revoked` | unknown or revoked device |
| `401` | `clock_skew` | timestamp outside accepted window |
| `401` | `bad_signature` | invalid HMAC/authenticated request |
| `401` | `replay` | nonce already consumed |
| `403` | `scope` | device lacks required scope |

Only `revoked` means the client should discard its stored credential and pair again.

A replay error can be retried once with a fresh nonce.

### v2 Device Revocation

A paired device can revoke itself with:

```text
DELETE /v2/device
```

Successful self-revocation returns:

```json
{
  "revoked": true
}
```

Observer destroys the stored HMAC credential for that device.

Subsequent requests from that device return:

```json
{
  "error": "revoked"
}
```

### v2 Interoperability Vectors

Reference vectors are stored in:

```text
vectors/v2-hmac.json
vectors/v2-spki.json
vectors/v2-sample-cert.pem
vectors/v2-qr.json
vectors/v2-qr.txt
```

`v2-hmac.json` contains a deterministic HMAC-SHA256 request-signing vector.

`v2-spki.json` and `v2-sample-cert.pem` contain the P-256 SPKI pin interoperability vector.

`v2-qr.json` and `v2-qr.txt` contain the sample pairing URI.

The sample certificate private key is not included.

### v2 Discovery

The pairing format reserves the Bonjour service type:

```text
_logos-observer._tcp
```

The current reference implementation includes the optional Bonjour instance in pairing metadata but does not yet advertise the service automatically.

Bonjour advertisement is release/integration work rather than part of the cryptographic protocol.

### v2 Security Boundary

Observer v2 must never become a generic proxy to localhost.

The only allowed upstream operations are explicit read-only mappings implemented in the reference code.

Current v2 mapping modules expose only selected node, network, mining, and rewards data.

Do not add generic forwarding such as:

```text
/v2/proxy?path=<anything>
```

Control operations remain out of scope for the current read-only client protocol.

## v1 Network Architecture

Typical deployment:

```text
                    LAN

client ─────────────────────────► Logos Observer
                                  192.168.x.x:8081
                                         │
                                         │ localhost HTTP
                                         ▼
                                  Logos node API
                                  127.0.0.1:8080
```

The Logos API itself should remain localhost-only.

Observer is not an arbitrary proxy.

It translates selected Logos node data into a deliberately small, stable client-facing API.

## v1 `/v1/status`

After authentication and decryption, a response looks approximately like:

```json
{
  "version": 1,
  "node": {
    "state": "Online",
    "phase": "Following",
    "height": 9210,
    "slot": 123456,
    "libSlot": 123400
  },
  "network": {
    "connectedPeers": 42,
    "discoveredPeers": 108
  }
}
```

Clients should depend on this Observer schema rather than raw Logos API structures.

## v1 Pairing Model

Pairing begins with a short-lived QR code generated by the node operator.

The QR contains:

- protocol version
- Observer LAN address
- device ID
- temporary 256-bit bootstrap secret
- expiration timestamp

The bootstrap secret is only valid for pairing.

The client generates a new random 256-bit permanent root secret locally.

That permanent secret is encrypted and delivered to Observer during authenticated pairing activation.

After successful activation:

```text
temporary QR bootstrap secret
              │
              ▼
            deleted
```

The permanent device secret is **not contained in the QR**.

An old QR cannot be reused after successful pairing.

## v1 Protocol

Protocol identifier:

```text
logos-observer-v1
```

Observer v1 uses:

- SHA-256
- HKDF-SHA256
- HMAC-SHA256
- AES-256-GCM

### HKDF salt

```text
logos-observer-v1
```

### Permanent-device key domains

Derived from the permanent root secret:

```text
request-auth
response-aead
```

### Pairing key domains

Derived from the temporary bootstrap secret:

```text
pairing-request-auth
pairing-request-aead
pairing-response-aead
```

Separate derived keys are used for separate cryptographic purposes.

## v1 Encoding Rules

Strings are UTF-8.

Canonical cryptographic fields are separated with exactly one:

```text
LF / 0x0a
```

There is no trailing LF.

Base64 values use URL-safe Base64 without `=` padding.

HMAC digests are lowercase hexadecimal.

Request nonces are 16 random bytes encoded as 32 hexadecimal characters.

AES-GCM nonces are 12 random bytes.

## v1 Request Authentication

Authenticated requests include:

```text
X-Observer-Version
X-Observer-Device
X-Observer-Time
X-Observer-Nonce
X-Observer-Signature
```

Canonical request:

```text
logos-observer-v1
<device ID>
<METHOD>
<path>
<Unix timestamp>
<request nonce>
<SHA256 exact request body>
```

The canonical request is authenticated using HMAC-SHA256 with the derived `request-auth` key.

## v1 Replay Protection

Current policy:

```text
request freshness: approximately ±60 seconds
nonce retention:   approximately 5 minutes
```

Used request nonces are persisted in SQLite.

Replay protection therefore survives Observer process restarts.

## v1 Encrypted Responses

Authenticated responses use AES-256-GCM.

Response envelope:

```json
{
  "v": 1,
  "alg": "A256GCM",
  "nonce": "<base64url>",
  "ciphertext": "<base64url ciphertext + tag>"
}
```

Relevant response headers:

```text
X-Observer-Version: 1
X-Observer-Encryption: A256GCM
X-Observer-Response-Time: <Unix timestamp>
X-Observer-Request-Nonce: <original request nonce>
```

AES-GCM Additional Authenticated Data binds the encrypted response to:

```text
logos-observer-v1
A256GCM
<device ID>
<request method>
<request path>
<request nonce>
<HTTP status>
<response timestamp>
```

Modifying the ciphertext or authenticated request context causes AES-GCM verification to fail.

## v1 Pair Activation

Observer's intentional POST endpoint is:

```text
POST /v1/pair/activate
```

This does **not** modify the Logos node.

It only establishes local Observer pairing state.

Normal node-data endpoints remain read-only.

## v1 Device Credentials

Each paired client receives an independent credential.

Example:

```text
Node A
├── iPhone -> root secret A1
└── iPad   -> root secret A2

Node B
└── iPhone -> root secret B1
```

There is no global application credential.

A device remains authorized until explicitly revoked.

## Security Boundary

Observer must never become a generic localhost proxy.

Do not add an endpoint such as:

```text
/v1/proxy?path=<anything>
```

New capabilities should instead be explicitly implemented as narrow read-only endpoints, for example:

```text
/v1/status
/v1/network
/v1/blend
/v1/mining
/v1/rewards
```

Only add them after verifying that the underlying Logos operations are read-only.

Observer should never expose functionality for:

- transaction submission
- wallet/key export
- node private keys
- node configuration changes
- arbitrary RPC
- arbitrary filesystem access
- arbitrary localhost HTTP access

## Privacy Model

Normal data flow remains local-first:

```text
client
   ⇅
user's Logos Observer
   ⇅
user's Logos node
```

There is no application-developer backend in the Observer data path.

v1 uses application-layer AES-256-GCM response encryption.

v2 uses TLS 1.3 for transport confidentiality and integrity, plus HMAC-SHA256 request authentication for device authorization and replay protection.

A passive LAN observer can still observe metadata such as:

- source and destination IP addresses
- TCP port
- timing
- approximate packet sizes

For v2, TLS also protects HTTP paths, headers, and bodies from passive network observation.

## v1 iOS Integration

The protocol maps cleanly to CryptoKit:

```text
HKDF<SHA256>
HMAC<SHA256>
AES.GCM
SHA256
```

The permanent root secret should be stored in iOS Keychain.

A stored connection needs approximately:

```text
baseURL
deviceId
rootSecret
protocolVersion
```

Expected UX:

```text
Add Logos Node
      ↓
Scan QR
      ↓
Connected
      ↓
View node status
```

## Running

The raw Logos API is expected at:

```text
127.0.0.1:8080
```

### Run v2 locally

Create an environment:

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
```

Run Observer v2 using its default port:

```bash
./.venv/bin/python v2_server.py \
  --host 192.168.1.20 \
  --advertise-host 192.168.1.20 \
  --port 8081 \
  --state-dir .v2-state \
  --upstream http://127.0.0.1:8080
```

Generate a five-minute pairing offer locally:

```bash
./.venv/bin/python v2_pair_cli.py \
  --state-dir .v2-state \
  --host 192.168.1.20 \
  --port 8081 \
  --name "Observer"
```

Do not expose pairing material through a network endpoint.

Do not publish a live bootstrap URI.

### Run v1 and v2 side by side

For migration/testing, keep v1 on `8081` and explicitly stage v2 on another port:

```bash
./.venv/bin/python v2_server.py \
  --host 192.168.1.20 \
  --advertise-host 192.168.1.20 \
  --port 8443 \
  --state-dir .v2-state \
  --upstream http://127.0.0.1:8080
```

Once v2 becomes the primary protocol, `8081` remains its default port.

Production installations should:

- run Observer as a dedicated unprivileged service account
- keep the raw Logos API bound to loopback
- use a persistent state directory
- protect the TLS private key and device database
- restrict the Observer port to the intended trusted network with the host firewall
- avoid exposing the Observer directly to the public Internet unless the threat model and deployment have been reviewed

The live reference deployment has been tested with a dedicated `logos-observer` service account and LAN-restricted firewall access.

## Dependencies

Runtime requirements:

- Python 3
- `cryptography`

SQLite and HTTP client/server functionality use Python/system libraries.

`qrencode` is optional for terminal rendering of the v2 pairing URI.

The pairing URI itself can always be printed without `qrencode`.

## Development Status

This repository contains:

- the original Observer v1 reference implementation in `observer.py`
- the Observer v2 reference implementation
- v2 TLS/SPKI identity handling
- v2 pairing and scoped device state
- v2 request authentication and persistent replay protection
- v2 sanitized Logos node mappings
- v2 combined and dedicated read routes
- deterministic interoperability vectors
- automated protocol and integration tests

The v2 implementation has been exercised against a running Logos node over a real LAN connection.

The current automated suite contains 47 passing tests.

The remaining work is primarily release and client interoperability work:

- Casberi integration/interoperability testing
- Bonjour advertisement
- deployment packaging/documentation refinement
- final v1-to-v2 migration planning
- release/versioning decisions

No generic proxy behavior should be added during that work.

## License

No license has been selected yet.
