# Changelog

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

