# Security and privacy

Grok Usage Pet is local-first and has no telemetry, analytics, advertising,
crash-reporting service, or machine fingerprinting. Optional update checks
query only the GitHub Releases API for this repository. Installing an update
requires an explicit click, HTTPS, a strict versioned filename allowlist, an
immutable GitHub Release, matching API asset digests, and a matching SHA256
checksum file. There is no silent replacement and no other update server.

## Local credentials

The app does not require a separate account. It uses existing local sessions:

- Reads the first Grok account from `GROK_HOME/auth.json`, or
  `%USERPROFILE%\.grok\auth.json` by default.
- Opens Cursor's `state.vscdb` in read-only SQLite mode to obtain the local
  access token and account metadata.
- Never writes to Cursor's database.
- Reads ChatGPT-login Codex credentials from `%USERPROFILE%\.codex\auth.json`
  (or `CODEX_HOME`). It never copies that file into a release and never stores
  `access_token`, `refresh_token`, or `account_id` in usage snapshots.
- When a Grok access token expires, follows the account's OIDC discovery
  metadata, refreshes the token, and atomically updates the existing Grok
  `auth.json`. The issuer and token endpoint must be `https://auth.x.ai`
  (no other host, scheme, port, or userinfo). On platforms that support POSIX
  modes, private file permissions are preserved.
- When a Codex access token expires, refreshes it at `https://auth.openai.com`
  and writes the updated tokens back to the existing Codex `auth.json`. API Key
  Codex mode has no remaining-percentage pool and is treated as unavailable.
- Before replacing either auth file, verifies that another process has not
  changed it since it was read. On Windows, replacement uses `ReplaceFileW` to
  preserve DACLs, encryption, and named streams; on POSIX, private mode bits
  are preserved.

## Network access

Quota retrieval contacts only:

- the Grok account's configured OIDC issuer (normally `https://auth.x.ai`) for
  discovery and token refresh;
- `https://cli-chat-proxy.grok.com` for SuperGrok billing and settings;
- `https://api2.cursor.sh` for Cursor and Grok Bot quota information;
- `https://auth.openai.com` to refresh a ChatGPT-login Codex session;
- `https://chatgpt.com/backend-api/wham/usage` for Codex 5-hour and weekly
  remaining percentages;
- `https://api.github.com/repos/liruilong0805/grok-usage-pet/releases/latest`
  when update checks are enabled, plus GitHub download hosts for the versioned
  Windows zip and `.sha256` files after the user chooses to install.

The OIDC token endpoint is discovered dynamically from the configured issuer,
so it is not necessarily a single fixed URL.

The app does not upload source code, project files, chats, or prompts.
GitHub CDN redirects are accepted only when they originate from an allowlisted
versioned release-asset URL; arbitrary CDN URLs cannot be requested directly.

## Local data

The app stores UI state, logs, and the last usable quota snapshot under
`%LOCALAPPDATA%\GrokUsagePet`. On first v0.3 run it copies state and snapshots
from the historical `%LOCALAPPDATA%\GrokUsagePetKawaii` directory only when the
new destination file does not already exist. A quota snapshot can contain
Cursor email, plan/status metadata, reset times, and service error details.
Treat these files as private local data. Command-line refreshes report only
whether the local snapshot was updated; they do not print authenticated quota
values or provider error details to stdout/stderr. The plain-text summary also
omits provider error details.

If Cursor launch integration is enabled, the app updates
`%USERPROFILE%\.cursor\hooks.json`. It preserves unrelated fields and removes
only entries marked `managedBy: grok-usage-pet`.

Settings → 卸载, or `pet.py --uninstall` / `GrokUsagePet.exe --uninstall`,
removes those autostart hooks, the GrokUsagePet scheduled tasks (including the
legacy kawaii names), any running pet or watcher instances, the desktop
shortcut, and the `%LOCALAPPDATA%\GrokUsagePet` / `GrokUsagePetKawaii` data
directories. It never deletes Grok, Cursor, or Codex login files. A frozen
portable release also deletes its own folder after exit only when the folder has
the pack-time marker, exact release-directory format, expected executable and
runtime, and contains no symbolic links or Windows reparse points. Source clones,
renamed folders, and unmarked directories are never recursively deleted.

## Release safety

Tests are offline and use temporary credentials. The release script rejects
credential databases, quota snapshots, state files, and logs before creating
the ZIP. Published archives include a SHA256 checksum, exact third-party
license copies, and GitHub build-provenance attestations. Skin sprite sheets
must be bounded WebP images; untrusted manifest dimensions and animation
values are clamped to safe limits. GitHub CodeQL default setup scans Python and
GitHub Actions on protected-branch pushes and weekly.

In-app updates reject path traversal, symbolic links, Windows special names,
case-colliding paths, excessive entry counts, and excessive aggregate expanded
size. The new tree is copied beside the current installation and smoke-tested;
the current app exits only after an explicit preflight readiness signal. A
failed preflight keeps the current tree running and restores the watcher, while
a failed switch restores and restarts the old tree. Staging, readiness, and
helper files are removed on completion or failure.

## Reporting a vulnerability

Do not open a public issue containing credentials, database contents, logs, or
private paths. Use the repository's
[private vulnerability report](https://github.com/liruilong0805/grok-usage-pet/security/advisories/new)
and send only a minimal reproduction with all secrets and personal data removed.
