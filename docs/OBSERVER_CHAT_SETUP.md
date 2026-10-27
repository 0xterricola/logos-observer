# Observer — Basecamp Chat to Casberi (CLI Setup)

**Status:** Current CLI-based setup (developer preview)  
**Tested setup:** macOS (Apple Silicon), Logos Basecamp Chat, local JSON-RPC bridge, and a Casberi iOS build supporting Observer v2 Chat pairing  
**Purpose:** Read your existing Basecamp Chat conversations in Casberi on the same local network.

This guide uses the **standalone Observer v2 Python CLI**. You do **not** need to build or install the separate `observer` or `observer_ui` Basecamp plugins for this Chat-only setup. No automatic UI setup or service management is assumed.

**Current limitation:** This connection is **read-only**. Keep using Basecamp Chat on your computer to send messages. Your computer, Basecamp Chat, local bridge, and Observer must stay running while Casberi reads chats.

## What you need

- A Mac with **Logos Basecamp** installed and **Chat already working** (open Chat and confirm your conversations are visible). Install Basecamp using the [official instructions](https://docs.logos.co/basecamp/install-logos-basecamp) if needed.
- A compatible **Casberi iOS/TestFlight build** that supports Observer v2 and the `chat.read` capability, installed on your iPhone.
- The **Logos JSON-RPC bridge** (`json_rpc_bridge`) installed and loaded in the **same Basecamp instance** as Chat, listening at **`127.0.0.1:8645`**. The Observer repository does **not** install this module automatically. Obtain and install it via your Basecamp module distribution or from its maintainer before continuing. No verified public download command is provided here.
- Git, Python 3 with `venv` and `pip`, a terminal, and an internet connection for the initial install.
- Mac and iPhone on the **same trusted Wi-Fi/LAN**. Avoid guest networks, VPN isolation, and networks that block device-to-device connections.
- Optional: `qrencode` to print a scannable QR directly in Terminal.

You do **not** need to create another Chat identity or register another RLN membership for Observer. Use the existing working Basecamp Chat session. You do not need to start a separate `logosctl` Chat daemon.

## Step 1 — Check Basecamp Chat and the local bridge

Open Basecamp, load **Chat**, and check that your conversations appear. Ensure the `json_rpc_bridge` core module is loaded in **Settings → Module Inspector** (if installed). Do not expose its port to your network; it must remain localhost-only.

In Terminal, check the bridge port:

```bash
nc -z 127.0.0.1 8645 && echo "Bridge port is reachable"
```

**Expected:** `Bridge port is reachable`. This tests only whether the local port is open; it does **not** establish that the Chat module is initialized or returning conversations. If the command fails, resolve the Basecamp bridge installation/loading before continuing.

## Step 2 — Download Observer

Run these commands in Terminal:

```bash
mkdir -p ~/Developer
cd ~/Developer
git clone https://github.com/0xterricola/observer.git
cd observer
```

If you already cloned the repository, use your existing copy instead; do not clone over it.

The CLI implementation is in `v2_server.py` and `v2_pair_cli.py`. No `.lgx` package or Nix build is required for this CLI path.

## Step 3 — Install the Python dependency

From inside the `observer` directory:

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
```

The repository currently declares `cryptography` as its Python dependency. Keep using the `.venv/bin/python` executable in the commands below.

## Step 4 — Determine the Mac's LAN address

With your Mac on the same Wi-Fi/LAN as the iPhone:

```bash
LAN_IP=$(ipconfig getifaddr en0)
printf 'Mac LAN IP: %s\n' "$LAN_IP"
```

**Expected:** an address such as `192.168.1.20` (yours will be different). If it is empty, `en0` is not your active interface; find your current LAN IP in **System Settings → Network** and use it manually for `LAN_IP`:

```bash
LAN_IP="192.168.1.20"
```

Replace that example with your **actual** Mac LAN IP. Run the command that sets `LAN_IP` again in **each new Terminal tab**, because shell variables do not carry across tabs.

## Step 5 — Start the Chat-capable Observer

Keep Basecamp Chat and the JSON-RPC bridge running. In **Terminal tab 1**, from the repo directory:

```bash
cd ~/Developer/observer
LAN_IP=$(ipconfig getifaddr en0)

./.venv/bin/python v2_server.py \
  --host 0.0.0.0 \
  --port 8444 \
  --advertise-host "$LAN_IP" \
  --state-dir .v2-state-chat-dev \
  --chat-bridge http://127.0.0.1:8645/rpc
```

**Expected output:** Observer reports that HTTPS is listening, its advertised endpoint, its SPKI pin, and **TLS 1.3 only**. Leave this terminal running. The command creates or reuses the Observer's TLS key and persistent pairing/device state in `.v2-state-chat-dev`.

The port `8444` is the Chat preview example, not the protocol default. Do not forward this port on your router or expose it to the public internet.

### Verify the HTTPS health endpoint

In **Terminal tab 2**, while Observer is still running in tab 1:

```bash
cd ~/Developer/observer
LAN_IP=$(ipconfig getifaddr en0)

curl --silent --show-error --fail --max-time 5 \
  --cacert .v2-state-chat-dev/observer-v2-cert.pem \
  "https://${LAN_IP}:8444/health"
```

**Expected:**

```json
{"ok":true,"service":"logos-observer","protocol":"logos-observer-v2"}
```

This confirms the local Observer HTTPS health endpoint and certificate trust. **It does not confirm that Basecamp Chat reads are available**; that is verified after pairing in Casberi. Do not use `curl -k` to bypass certificate verification.

## Step 6 — Create a Chat-only pairing QR

In **Terminal tab 2**, with tab 1 still running:

```bash
cd ~/Developer/observer
LAN_IP=$(ipconfig getifaddr en0)

./.venv/bin/python v2_pair_cli.py \
  --state-dir .v2-state-chat-dev \
  --host "$LAN_IP" \
  --port 8444 \
  --name "Basecamp Chat" \
  --scope chat.read
```

**Expected:** a pairing URI beginning with `logos-observer://pair`, a certificate SPKI pin, an expiration time, and a scope of **`chat.read` only**. If `qrencode` is on your PATH, the command also displays a terminal QR code.

If you see `qrencode not installed`, on a Mac with Homebrew you can install it with:

```bash
brew install qrencode
```

Then **rerun the pairing command** to produce a fresh QR. You do not need `qrencode` to run the Observer server; it is only for the QR display.

**Important:** The QR / pairing URI contains a temporary pairing secret. It expires after **five minutes** and is intended for one successful pairing. Do not post it in screenshots, chat, GitHub issues, or logs shared with others. If it expires, run the pairing command again.

## Step 7 — Pair Casberi on your iPhone

1. Put the iPhone on the **same LAN** as your Mac.
2. Open a compatible **Casberi** build and its **Observer pairing / add connection** flow (labels may differ by build).
3. Scan the QR displayed in Terminal.
4. Review the requested capability; use **Chat read-only (`chat.read`)**.
5. Complete pairing in Casberi, then open its Chat/conversations view.

**Expected:** Casberi shows the conversations available through your active Basecamp Chat session. Messages received in Basecamp Chat should subsequently appear in Casberi while everything remains running. Sending from Casberi is **not** supported by this tested Chat-read integration.

## Step 8 — Confirm messages are updating

With Basecamp Chat, the bridge, Observer, and Casberi running:

1. Confirm existing conversations and messages load in Casberi.
2. Receive a new message in **Basecamp Chat** from a test contact.
3. Check that the message appears in Casberi without manually re-pairing.

An HTTPS health response alone is not enough: **this is the actual end-to-end Chat verification**.

## Stopping and restarting

To stop the standalone Observer, press **Ctrl+C** in Terminal tab 1. This does **not** stop Basecamp Chat or unregister your RLN membership.

To restart, use the same **Step 5** command and the **same state directory** (`.v2-state-chat-dev`). Previously paired devices can retain their Observer identity and authorization. Don't delete or publish the state directory: it contains a persistent private TLS key and device/authentication state. If you intentionally reset it, expect to pair again.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| `nc -z 127.0.0.1 8645` fails | Basecamp's `json_rpc_bridge` must be installed **and loaded**, and bound to localhost. Verify that Basecamp Chat is running. |
| `ipconfig getifaddr en0` prints nothing | Get the LAN IP from macOS Network settings, then set `LAN_IP="YOUR_IP"` in each terminal tab. |
| Observer reports address already in use | Something else occupies port `8444`; stop that instance or choose another port in **both** the server and pairing command. |
| HTTPS health request fails | Confirm the Observer terminal is still running, the chosen LAN IP and port match, and the certificate path exists. Avoid bypassing TLS validation. |
| Pairing QR does not appear | Install `qrencode` with Homebrew, then create a **new** pairing offer. |
| Pairing fails / expires | Use a new QR within five minutes; ensure the iPhone reaches the Mac over the LAN, macOS firewall allows the Observer server, and VPN/guest-network isolation is disabled. Do not ignore an identity mismatch. |
| Casberi connects but has no chats | Confirm Basecamp Chat conversations are loaded and the JSON-RPC bridge has access to the correct Basecamp instance. Observer `/health` does not diagnose this. |
| Chat works in Basecamp but not on phone | Check both devices are on the same LAN, that the Chat bridge and Observer remain running, and that the pairing offered `chat.read`. |
| Sending from Casberi is unavailable | Expected for the current read-only integration; send through Basecamp Chat. |

## Security notes

- This setup gives the paired mobile device access to **decrypted Chat content** via an explicitly authorized read-only capability. Pair only devices you trust.
- Observer protects its connection with TLS 1.3, a pinned public-key identity, device credentials, and request authentication.
- The JSON-RPC Chat bridge stays bound to `127.0.0.1`; do **not** bind it publicly or forward it on your router.
- The pairing QR is **sensitive, temporary authorization material**, not something to share as a screenshot.
- No wallet, RLN registration, Chat signing keys, or outbound Chat operations are required **by Observer**.
- Current connection is **local-network only** in this guide. There is no cloud relay or remote-access setup here.

## References

- [Observer repository and CLI documentation](https://github.com/0xterricola/observer)
- [Observer v2 pairing CLI source](https://github.com/0xterricola/observer/blob/main/v2_pair_cli.py)
- [Observer v2 server source](https://github.com/0xterricola/observer/blob/main/v2_server.py)
- [Official Basecamp installation documentation](https://docs.logos.co/basecamp/install-logos-basecamp)
- [Official Basecamp module installation documentation](https://docs.logos.co/basecamp/install-and-load-a-module-in-logos-basecamp)
