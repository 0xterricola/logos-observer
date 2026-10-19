# Logos Observer — Basecamp Chat → Casberi Setup Guide

**Status:** Target user experience / planned onboarding flow  
**Audience:** People who use Basecamp Chat and want to read their chats on a phone  
**Goal:** Connect Casberi to an existing Basecamp Chat session **without using Terminal, copying certificates, or configuring network ports**.

> **Important:** This document describes the experience we want to ship, **not the setup available today**. The current integration works with a separately started Observer and technical configuration. One-click startup, automated configuration, in-app QR display, and device management are not yet complete.

## The intended experience

**Open Basecamp Chat → Connect Mobile Device → Enable Observer → Scan QR in Casberi → Read messages.**

### Before you begin

- Basecamp is installed on your computer and Chat opens with your existing conversations.
- Casberi is installed on your iPhone, using a build that supports Observer pairing and reading Chat.
- Your computer and iPhone are connected to the same local network for the initial release.
- Your computer stays powered on, Basecamp Chat remains available, and Observer is running while your phone accesses those chats.

You **do not** need to create a second Chat account or register a separate RLN membership for Observer. Basecamp Chat remains responsible for Chat identity and sending messages. Observer provides an authorized, read-only connection for the phone.

## Setup: step by step

### 1. Open Basecamp Chat

Launch **Basecamp** on your computer and open **Chat**. Check that your conversations load.

**Expected result:** You can see your existing Chat conversations in Basecamp.

If Chat isn't set up, complete its normal onboarding first. Observer should not substitute for Chat account setup.

### 2. Choose “Connect Mobile Device”

In Basecamp Chat, open **Settings → Connect Mobile Device** (proposed navigation). Basecamp opens **Observer Manager** or offers to install/enable it as part of the guided flow.

The page explains:

> **Connect your phone to Basecamp Chat**  
> Logos Observer makes your existing conversations available to an authorized mobile app. Your Chat identity stays with Basecamp. Mobile access is read-only in this release.

Select **Get Started**.

**Expected result:** The setup assistant opens without asking for an HTTPS URL, a certificate path, or an SPKI pin.

### 3. Check the Chat connection

Observer Manager checks the required components automatically:

- Basecamp Chat is available.
- The Chat integration exposes the necessary read-only methods.
- The local Chat bridge can retrieve permitted conversation data.

Show a simple result such as **Chat connected**. If a check fails, provide one understandable action (for example, **Open Chat**, **Enable Chat Integration**, or **Try Again**).

**Expected result:** A clear **Ready to enable Observer** state. The user does not interact with JSON-RPC or manually configure a bridge.

### 4. Enable Observer

Select **Enable Observer**.

Observer Manager automatically:

1. Creates or loads an Observer configuration and TLS identity.
2. Connects its read-only Chat source to the existing Basecamp Chat integration.
3. Starts an Observer instance **owned by Basecamp** (without taking over an independently running Observer).
4. Checks its health, TLS identity, and Chat availability separately.

**Expected result:** **Observer running** and **Chat available** appear in the UI. The user should see a short, actionable error if either check fails.

For users who intentionally operate their own Observer, **Advanced Settings** may offer **Connect to an existing Observer** instead of starting another instance.

### 5. Pair Casberi with a QR code

In Observer Manager, select **Connect Phone** to display a **pairing QR code**.

On your iPhone:

1. Open **Casberi**.
2. Choose **Connect to Observer** (proposed wording; exact labels may change).
3. Scan the QR code on the computer.
4. Review and approve the requested **Chat read-only** access.

The pairing flow establishes the Observer endpoint, verifies its TLS identity, and grants only the scope needed to read Chat. It must not expose wallet keys, Chat signing material, or Observer private TLS keys in the QR code.

**Expected result:** Both apps show **Connected**, with the paired phone listed in Observer Manager.

### 6. Read messages on your phone

In Casberi, open **Chat**. Existing authorized conversations and message history load, and incoming messages appear while the computer, Basecamp Chat, and Observer remain available.

**Expected result:** A message received by Basecamp Chat also appears in Casberi without manual refresh.

**Current feature boundary:** The working Casberi/Observer integration provides **read-only Chat access**. Sending messages from Casberi is not part of this initial setup milestone and must not be presented as available until independently verified.

### 7. Manage or disconnect your phone

In **Observer Manager → Connected Devices** (planned screen), the user can:

- See which devices have Chat read-only access.
- Disconnect a phone or revoke its authorization.
- Connect another phone through a new pairing flow.
- Disable the Basecamp-managed Observer without disrupting Basecamp Chat.

**Expected result:** Revoked devices can no longer read Chat through Observer. Independently managed Observer instances are never stopped by Basecamp's service controls.

## What the finished setup screen should show

| Item | Healthy state | What it means |
|---|---|---|
| Basecamp Chat | **Connected** | Existing Chat account and conversations are available. |
| Chat bridge | **Available** | Observer can read authorized Chat information. |
| Observer | **Running** | The HTTPS service is reachable. |
| Observer identity | **Verified** | The mobile client can authenticate the expected Observer identity. |
| Mobile device | **Connected — Read-only** | Casberi is paired with the required permission. |

These are **separate checks**: an HTTPS health response does not, by itself, prove that the Chat bridge or chat-history retrieval is working.

## Troubleshooting language for users

| User sees | Guidance |
|---|---|
| **Chat not connected** | Open Basecamp Chat and make sure your conversations load, then retry. |
| **Chat integration unavailable** | Use **Enable Chat Integration** or follow the in-app repair flow. |
| **Observer not running** | Select **Try Again**; show technical logs only in Advanced Diagnostics. |
| **Phone cannot connect** | Put your iPhone and computer on the same local network and check that Observer is running. |
| **Observer identity changed** | Re-pair from Observer Manager; never bypass certificate or identity verification. |
| **Messages are not updating** | Verify Basecamp Chat, the read-only bridge, and Observer separately. |
| **Sending from Casberi unavailable** | Read messages on Casberi; send messages from Basecamp Chat for now. |

## Design and security requirements

- **No Terminal required** for the normal user journey; no manual IP address, port, PEM path, or SPKI pin entry.
- **No duplicate Chat identity or RLN registration** created by Observer. Existing Basecamp Chat remains the source of truth.
- **Read-only, least-privilege scope:** pairing grants `chat.read` only when approved; do not expose other Observer data without authorization.
- **TLS identity verification is mandatory.** Never fall back to an insecure connection to make pairing appear successful.
- **Keep secrets out of pairing payloads and logs.** Private keys and signing material remain outside Observer's read-only responsibilities.
- **Ownership-aware service controls:** start/stop only the Observer process managed by Basecamp; preserve independently running CLI services.
- **CLI/API parity:** the graphical path simplifies setup but does not remove or limit standalone/headless operation.
- **Clear state and revocation:** tell users whether a phone is authorized, whether Chat is available, and how to revoke access.

## Release checklist — do not publish this as a live how-to until verified

- [x] Standalone Observer can provide read-only Chat data through the Basecamp Chat bridge.
- [x] Casberi has displayed existing messages and incoming updates in the working integration.
- [x] Native `logos_observer` module and Observer Manager UI are installable in Basecamp.
- [x] Observer Manager can check the standalone Observer's HTTPS health and TLS identity.
- [ ] Provide an obvious entry point from Basecamp Chat to Observer onboarding.
- [ ] Detect/enable the Chat bridge automatically, without terminal commands.
- [ ] Start/configure/stop a Basecamp-owned Observer without affecting standalone instances.
- [ ] Make Observer Chat availability a separate, correctly scoped status indicator.
- [ ] Generate and display a correct, permission-scoped Casberi pairing QR in Basecamp.
- [ ] Verify the complete nontechnical pairing flow on a fresh Basecamp installation.
- [ ] Add device authorization listing and revocation.
- [ ] Verify user-facing failure and recovery states, including identity change and offline operation.
- [ ] Keep advanced connection settings available for manually managed installations.

## Definition of done

A new user with **an already functioning Basecamp Chat account** can open Basecamp, enable Observer, pair Casberi, and receive new chat messages on an iPhone **without opening Terminal, editing a configuration file, registering another RLN membership, or handling certificates manually**. They can later revoke the phone's access from a graphical screen, and disabling Observer does not interrupt Basecamp Chat.
