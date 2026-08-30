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
- When a Grok access token expires, follows the account's OIDC discovery
  metadata, refreshes the token, and atomically updates the existing Grok
  `auth.json`. On platforms that support POSIX modes, private file permissions
  are preserved.

## Network access

Quota retrieval contacts only:

- the Grok account's configured OIDC issuer (normally `https://auth.x.ai`) for
  discovery and token refresh;
- `https://cli-chat-proxy.grok.com` for SuperGrok billing and settings;
- `https://api2.cursor.sh` for Cursor and Grok Bot quota information.

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

## Release safety

Tests are offline and use temporary credentials. The release script rejects
credential databases, quota snapshots, state files, and logs before creating
the ZIP. Published archives include a SHA256 checksum.

## Reporting a vulnerability

Do not open a public issue containing credentials, database contents, logs, or
private paths. Send a minimal reproduction with all secrets and personal data
removed through a private contact channel listed on the maintainer's GitHub
profile.
