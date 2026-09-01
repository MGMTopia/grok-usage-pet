# Changelog

## Unreleased

- Add a confirmed in-app purge that removes autostart, shortcuts, and local
  quota data without touching Grok, Cursor, or Codex login files.

## 0.3.4 — 2026-09-01

Security and release-integrity patch. Git tag: `v0.3.4`.

- Upgrade Pillow from 11.0.0 to 12.3.0 to resolve current image-processing advisories.
- Accept only bounded WebP sprite atlases and sanitize untrusted skin dimensions, rows, frame counts, and timing.
- Abort OAuth credential writes when another process updates the auth file during refresh.
- Preserve Windows credential-file ACLs, encryption, and named streams with `ReplaceFileW`.
- Add a hash-locked Windows release dependency set and monthly Dependabot checks.
- Package exact Python, Tcl/Tk, Pillow, native image-library, and PyInstaller license terms.
- Pin GitHub Actions to immutable commit SHAs and separate read-only build permissions from release permissions.
- Generate GitHub build-provenance attestations and publish releases through a recoverable draft step.
- Remove workstation-specific Git metadata instructions from the public README.

## 0.3.3 — 2026-08-31

Quota, animation, launcher, and hardening release. Git tag: `v0.3.3`.

- Add Codex 5-hour and weekly remaining on one bar (dark = 5-hour, light = weekly) from local ChatGPT-login `~/.codex/auth.json`.
- Refresh Codex OAuth tokens locally; never store Codex tokens in usage snapshots.
- After a manual quit, do not autostart again until Grok Build or Cursor is restarted, or the user opens the pet.
- Play `failed` after every usable fetch below 20% remaining, and one-shot `waiting` above 20%.
- Play `waving` on first appearance, after a skin switch, and every 5 minutes without user input.
- Preserve real frame timing and smooth 16-direction look transitions across skins.
- Align quota rows (name, period tag, remaining) across SuperGrok, Cursor, and Codex.
- Fix the desktop shortcut so `pythonw` receives the pet script path without extra quotes.
- Tolerate Tk menu cleanup racing with application shutdown.
- Allow Grok OAuth refresh only against `https://auth.x.ai`.
- Keep skin ids and asset filenames inside `skins/<id>/`.
- Document Codex network endpoints in `SECURITY.md`.
- Add structured public feedback forms and contribution/privacy guidance.
- Require release tags to match `VERSION` before packaging.

## 0.3.1 — 2026-08-30

Theme and hover-behavior update. Git tag: `v0.3.1`.

- Let every skin select a validated, data-driven UI theme in `pet.json`.
- Give Original/Pip a cyan-on-navy technology theme with circuit decoration.
- Keep Megumi Kato visually distinct with the existing warm, soft card theme.
- Apply skin themes to quota cards, progress bars, reset tips, and settings.
- Treat fixed-open quota cards as a session-only interaction and discard legacy
  `pinned`/`expanded` state that could make the quota window appear stuck open.
- Document the theme manifest contract and retain safe fallbacks for older skins.

## 0.3.0 — 2026-08-29

Product and release-foundation update. Git tag: `v0.3.0`.

- Establish **Grok Usage Pet** as the product identity and remove `kawaii` from
  the executable, archive, scheduled-task, shortcut, and data-directory names.
- Add Pip, an original pixel robot, as the complete default theme.
- Keep Megumi Kato as an optional unofficial fan theme with a separate asset
  notice; the MIT license applies to code, not third-party character artwork.
- Load every theme from `skins/<id>/` and fall back safely to Original.
- Migrate existing state and snapshots from `GrokUsagePetKawaii` on first run
  without overwriting newer files.
- Add privacy/security documentation, repository hygiene checks, MIT licensing,
  Windows CI, and tag-driven GitHub Releases.
- Publish versioned Windows x64 archives with SHA256 checksums.

## 0.2.0 — 2026-08-29

Reliability release for the Kato Megumi kawaii line. Git tag: `v0.2.0`.

- Protect Grok auth refreshes with private, atomic file replacement.
- Preserve Cursor hooks and remove only entries explicitly managed by this app.
- Add explicit `complete`, `partial`, and `failed` snapshot states.
- Keep the last usable snapshot when every source fails.
- Add stable CLI exit codes: `0` usable, `1` no source available, `2` internal failure.
- Move Tk updates to the main thread through a result queue.
- Split usage formatting, snapshot storage, Cursor hooks, skins, and UI view mapping into focused modules.
- Add locked build dependencies, automated tests, package safety checks, and frozen executable smoke tests.
- Add a deterministic, offline `--visual-smoke-test` that renders the real Tk UI and exits automatically.
- Package the complete `skins` directory in the kawaii release.

## 0.1.0 — 2026-08-28

First GitHub kawaii snapshot (not tagged at the time): Kato Megumi pet, `skins/`, and dual-repo backup notes.
