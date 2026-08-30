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
    "accent": "#45DFF2",
    "bubbleFill": "#10243A"
  }
}
```

Built-in presets are `tech`, `soft`, and the compatibility-only `classic`.
Supported shape values are `rounded`/`classic` for `bubbleStyle`,
`rounded`/`square` for bars and tips, and `none`/`bow`/`circuit` for decoration.
Colors must use `#RRGGBB`; invalid presets, colors, or enum values safely fall
back to the soft preset. `radius` is clamped to 0–28.

Available color tokens include `bubbleFill`, `bubbleOutline`, `bubbleShadow`,
`label`, `labelHot`, `barTrack`, `barOk`, `barMid`, `barLow`, `percentage`,
`tipFill`, `tipOutline`, `tipTitle`, `tipText`, `spinner`, `accent`, `inner`, and
the `settingsBackground`/`settingsForeground`/`settingsMuted` family.

Themes affect the quota card, progress bars, reset tooltip, settings window,
and decorative mark. They do not affect quota fetching or credential access.
