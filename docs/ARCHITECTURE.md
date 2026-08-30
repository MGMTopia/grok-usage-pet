# Architecture

Grok Usage Pet has two independent product layers:

```text
Grok Usage Pet
├── Quota engine
│   ├── Grok OIDC and SuperGrok billing
│   └── Cursor and Grok Bot usage
└── Pet engine
    ├── Original theme
    └── Megumi Kato fan theme
```

## Quota engine

`fetch_usage.py` reads existing local sessions and normalizes provider results
into `complete`, `partial`, or `failed` snapshots. `snapshot_store.py` writes
usable snapshots atomically and retains the last usable result when every
provider fails.

## Pet engine

`skin_catalog.py` discovers theme manifests and assets. `pet.py` maps normalized
quota values into the Tk view model, selects animation rows, and resolves UI
tokens defined by the active theme. Each `pet.json` may select a `theme.preset`
and override validated colors, card, bar, tooltip, radius, and decoration styles.
Manifests without `theme` retain the soft compatibility preset. Themes use the
Codex-compatible v2 8×11 atlas contract: nine
standard animation rows and sixteen look directions.

The v0.3 structure makes `original` the default and keeps `megumi-kato`
optional. Core startup must remain functional when the fan theme is absent.

## Local integrations

The app can create Windows scheduled tasks and a managed Cursor `sessionStart`
hook. These integrations use stable ownership markers so disabling the feature
does not remove third-party configuration.
