# Theme manifests

Every skin keeps animation metadata and UI presentation in the same
`skins/<id>/pet.json` manifest. The optional `theme` object is resolved over a
built-in preset, so older third-party skins remain compatible.

```json
{
  "theme": {
    "preset": "tech",
    "bubbleStyle": "rounded",
    "barStyle": "rounded",
    "tipStyle": "rounded",
    "decoration": "circuit",
    "bubbleDecoration": "pcb",
    "accent": "#45DFF2",
    "bubbleFill": "#10243A"
  }
}
```

Built-in presets are `tech`, `soft`, and the compatibility-only `classic`.
Supported shape values are `rounded`/`classic` for `bubbleStyle`,
`rounded`/`square` for bars and tips, and `none`/`bow`/`circuit` for decoration.
`bubbleDecoration` controls only the small emblem above the quota bubble;
it accepts `none`, `bow`, `circuit`, `paw`, `beret`, or `pcb`. When omitted or
invalid, it follows `decoration` for backward compatibility. The main
`decoration` token still controls clock styling and menu marks; changing the
quota emblem does not alter those surfaces.
Colors must use `#RRGGBB`; invalid presets, colors, or enum values safely fall
back to the soft preset. `radius` is clamped to 0–28.

Available color tokens include `bubbleFill`, `bubbleOutline`, `bubbleShadow`,
`label`, `labelHot`, `barTrack`, `barOk`, `barMid`, `barLow`, `barLayerLight`,
`barLayerDark`, `percentage`, `tipFill`, `tipOutline`, `tipTitle`, `tipText`,
`spinner`, `accent`, `inner`, `muted`, and the
`settingsBackground`/`settingsForeground`/`settingsMuted` family.

Themes change colors, radius, bar/tip shape, and the decorative mark. Every
quota row shows the same content (name, period, remaining, reset on hover).
Single bars use `barOk` / `barMid` / `barLow` for remaining `>= 50` / `>= 20` /
`< 20`. The Codex 5-hour layer uses that exact fill. The week layer uses the
same remaining bands, then darkens slightly. They do not affect quota fetching
or credential access.

## Pack-ready skins

`pack-windows.ps1` copies the whole `skins/` tree into the zip. Only finished
themes belong there:

- `original` — default Pip
- `megumi-kato` — optional fan theme
- `chujiu` — 布偶猫初九

Older 初九 drafts (legacy / v3 / archive copies of v4) and experiments live
in `skins-archive/` or `work/` and are not packed. Copy a finished skin into
`skins/<id>/` only when it should ship.

`skins/<id>/app.ico` and `app.png` are the character portrait for that theme.
Appearance chips and a newly created desktop shortcut use that portrait.
The quota-bubble emblem (`bubbleDecoration`: PCB, beret, paw) is reused in
the right-click menu and Settings titlebar so those corners match the mark
above the usage panel.
