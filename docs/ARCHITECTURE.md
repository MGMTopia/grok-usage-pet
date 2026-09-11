# Architecture

Grok Usage Pet has two independent product layers:

```text
Grok Usage Pet
├── Pet engine
│   ├── Original theme
│   └── Megumi Kato fan theme
└── Information modules
    ├── Quota (SuperGrok, Grok Bot, Cursor, Codex)
    └── Clock (local time and stopwatch)
```

## Quota engine

`fetch_usage.py` reads existing local sessions and normalizes provider results
into `complete`, `partial`, or `failed` snapshots from SuperGrok, Cursor
(Grok Bot plus two monthly pools), and ChatGPT-login Codex. `snapshot_store.py`
writes usable snapshots atomically into the OS app-data folder and retains the
last usable result when every provider fails.

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

## Stage A core boundary

`UsagePet` keeps the existing UI lifecycle, but animation selection now passes
through the pure `resolve_animation_state()` resolver. Its compatibility order
is explicit and tested: drag direction, one-shot action, pointer look,
waiting, active refresh, quota review, then idle. Pointer look remains
available independently of quota modules.

Quota providers are optional information modules. When every provider switch
is off, the core skips refresh threads and remains in ordinary idle/interaction
behavior; it does not show a perpetual loading state.

`pet_settings.py` migrates v0.3 flat `pet_state.json` keys into `pet`,
`interaction`, `modules`, and `system` layers while keeping flat aliases
(`skin`, `x`, `y`, `enabled`, `check_updates`) so older readers still work.
The quota module lives at `modules.quota.enabled`. A broken quota blob must
not drop pet-core fields. Autostart remains in hooks and scheduled tasks, not
in this settings file.

`info_modules.py` hosts optional modules behind a refresh/permission
interface. `quota_module.py` calls `fetch_usage.py` and must catch provider errors.
`clock_module.py` is a local module: current time plus a themed alarm clock
(countdown or stopwatch). Tech skins draw a circuit chronometer; Kato/soft
skins draw a round twin-bell alarm. It does not refresh over the network.
When a countdown reaches zero the pet switches to the clock panel, shows a
topmost done banner, beeps, and may jump; waving and dragging still win.
Quota and clock are separate hover panels with a themed switcher. The host isolates a module that raises.
Disabled modules are not refreshed. Clock rows do not feed quota remaining
reactions. Module reactions still go through `resolve_animation_state()`, so
they cannot beat drag or an in-flight waving oneshot.

## Local integrations

The app can create Windows scheduled tasks and a managed Cursor `sessionStart`
hook. These integrations use stable ownership markers so disabling the feature
does not remove third-party configuration.

## Optional updates

`app_update.py` can query this repository's GitHub Latest Release. Installing
replaces only a frozen `GrokUsagePet.exe` tree after HTTPS, immutable-release
metadata, asset digest, SHA256, bounded extraction, and zip-layout checks. The
complete new tree is copied to a sibling directory and smoke-tested. The current
app exits only after the detached helper emits a preflight readiness signal; the
old directory is then renamed, and failures roll back to and restart the previous
tree. An enabled watcher is restored if preflight fails and re-registered after
the switch. The helper removes its readiness file and script. Source checkouts
open the release page and do not rewrite the working tree. There is no silent
replacement.
