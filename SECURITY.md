# Security and privacy

Grok Usage Pet is local-first and has no telemetry, analytics, advertising,
crash-reporting service, machine fingerprinting, or automatic updater.

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
  remaining percentages.

The OIDC token endpoint is discovered dynamically from the configured issuer,
so it is not necessarily a single fixed URL.

The app does not upload source code, project files, chats, or prompts.

## Local data

The app stores UI state, logs, and the last usable quota snapshot under
`%LOCALAPPDATA%\GrokUsagePet`. On first v0.3 run it copies state and snapshots
from the historical `%LOCALAPPDATA%\GrokUsagePetKawaii` directory only when the
new destination file does not already exist. A quota snapshot can contain
Cursor email, plan/status metadata, reset times, and service error details.
Treat these files as private local data.

If Cursor launch integration is enabled, the app updates
`%USERPROFILE%\.cursor\hooks.json`. It preserves unrelated fields and removes
only entries marked `managedBy: grok-usage-pet`.

Settings → 卸载, or `pet.py --uninstall` / `GrokUsagePet.exe --uninstall`,
removes those autostart hooks, the GrokUsagePet scheduled tasks (including the
legacy kawaii names), any running pet or watcher instances, the desktop
shortcut, and the `%LOCALAPPDATA%\GrokUsagePet` / `GrokUsagePetKawaii` data
directories. It does not delete Grok, Cursor, or Codex login files, and it does
not delete the program folder.

## Release safety

Tests are offline and use temporary credentials. The release script rejects
credential databases, quota snapshots, state files, and logs before creating
the ZIP. Published archives include a SHA256 checksum, exact third-party
license copies, and GitHub build-provenance attestations. Skin sprite sheets
must be bounded WebP images; untrusted manifest dimensions and animation
values are clamped to safe limits.

## Reporting a vulnerability

Do not open a public issue containing credentials, database contents, logs, or
private paths. Use the repository's
[private vulnerability report](https://github.com/liruilong0805/grok-usage-pet/security/advisories/new)
and send only a minimal reproduction with all secrets and personal data removed.
