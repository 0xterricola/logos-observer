# Install Observer in Logos Basecamp

Observer provides local-first monitoring and secure, read-only
access to Logos nodes and Basecamp Chat.

You can install Observer directly through Logos Basecamp's
Package Manager. No command-line tools, Nix builds, or manual
`.lgx` downloads are required.

## Supported platforms

- macOS ARM64 (Apple Silicon)
- Linux x86-64

Windows and other architectures are not currently packaged
for Observer.

## Prerequisites

- [Logos Basecamp](https://github.com/logos-co/logos-basecamp/releases)
  installed and running
- Internet access to download packages
- A portable Basecamp build compatible with the published packages

## 1. Open Package Manager

1. Launch Logos Basecamp.
2. Click **Package Manager** at the bottom of the sidebar.
3. Click **Manage Repositories** in the upper-right toolbar.

This opens **Settings > Package Repositories**.

## 2. Add the Observer repository

Under **Add a repository**, paste this URL:

```text
https://raw.githubusercontent.com/0xterricola/observer/main/logos-repo.json
```

Click **Add**.

Observer should appear in your repository list with the description:

> Local-first monitoring and secure read-only access for
> Logos nodes and Basecamp Chat.

Make sure the Observer repository is **Enabled**.

You only need to add this repository once. Basecamp saves
repository configuration between sessions.

## 3. Find the Observer packages

1. Return to **Package Manager**.
2. Search for `Observer`.
3. Locate the two packages under the **Observer** repository.

| Package | Type | Initial release |
| --- | --- | --- |
| Observer Core (`observer`) | `core` | `0.1.4` |
| Observer UI (`observer_ui`) | `ui_qml` | `0.1.3` |

These are the initial published versions. Newer versions may
be available in the catalogue.

Basecamp selects the appropriate package variant for your
operating system and architecture.

## 4. Install Observer Core

1. Find the Observer package with Type `core`.
2. Click **INSTALL**.
3. Review the **Install Package?** confirmation.
4. Click **Install**.
5. Wait for the package to show **INSTALLED**.

Observer Core provides the background service used by
the graphical interface.

## 5. Install Observer UI

1. Find the Observer package with Type `ui_qml`.
2. Click **INSTALL**.
3. Confirm the installation.
4. Wait for the package to show **INSTALLED**.

Install Core before UI so the backend is available.

If Basecamp shows **REINSTALL**, the corresponding version
is already installed. You do not need to reinstall it.

## 6. Load and open Observer

After installation:

1. Open **Settings > Module Inspector**.
2. Find Observer Core and click **Load** if it is not loaded.
3. Open **Settings > Apps Inspector**.
4. Find Observer UI and click **Load** if needed.
5. Open **Observer** from the Basecamp sidebar.

You can now use Observer's graphical setup and monitoring
interface.

For additional Chat configuration and pairing details, see
[Observer Chat Setup](OBSERVER_CHAT_SETUP.md).

## Updating Observer

Keep the Observer repository enabled in Basecamp.

When new versions are published, check Package Manager
for available updates to Observer Core and Observer UI.

Installing a new version may require reloading the modules
or restarting Basecamp.

Repository registration enables update discovery; it does
not mean that updates are installed silently.

## Troubleshooting

### Observer does not appear in Package Manager

- Confirm that the Observer repository is listed and Enabled
  under **Settings > Package Repositories**.
- Refresh the catalogue if the option is available.
- Check your internet connection.
- Make sure the repository URL was copied exactly.

### Package is marked Not available

A compatible package variant may not exist for your
operating system, architecture, or Basecamp build type.

Observer currently publishes portable packages for
macOS ARM64 and Linux x86-64.

If your Basecamp download source is restricted to
Logos Storage only, switch it to **Any** or **HTTP only**
under **Settings > Package Repositories**.

### Observer UI does not appear in the sidebar

- Verify Observer UI shows **INSTALLED**.
- Check **Settings > Apps Inspector**.
- Load the app if it shows **NOT LOADED**.
- Restart Basecamp if the sidebar has not refreshed.

### Observer UI cannot connect to Core

- Confirm Observer Core is installed.
- Check **Settings > Module Inspector**.
- Load Observer Core if necessary.
- Reopen the Observer UI.

### Already installed Observer manually?

If Package Manager shows **REINSTALL**, Basecamp already
recognizes the installed version.

You do not need to uninstall the existing modules simply
to add the repository. Avoid changing an existing working
installation unless an update or repair is necessary.

## Links

- [Observer source code](https://github.com/0xterricola/observer)
- [Observer releases](https://github.com/0xterricola/observer/releases)
- [Logos Basecamp](https://github.com/logos-co/logos-basecamp)
- [Official Basecamp module installation guide](https://docs.logos.co/basecamp/install-and-load-a-module-in-logos-basecamp)
