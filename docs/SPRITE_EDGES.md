# Windows sprite edges

The current Tk pet window uses the exact color key `#FF00FF` for transparent
desktop areas. Blending a semi-transparent sprite pixel against that key makes
an inexact purple color, which the Windows color key cannot remove.

`spriteEdgeMode` in `skins/<id>/pet.json` selects the common frame-conversion
strategy. Allowed values:

- `matte-free` (default for missing/invalid values): binary-key the sprite's
  original RGB at alpha >= 96, and use the exact key below that threshold.
  This prevents a purple matte without changing the sprite atlas. It is a
  suitable compatibility path for compact pixel mascots such as Chujiu.
- `legacy-matte`: retain the older partial-alpha blend onto the color key.
  Megumi explicitly keeps this mode until a true-alpha backend is available.

The mode is validated by `SkinCatalog.load_spec`, selected on skin activation,
and applied to all frames and fallback sprites in the shared Windows image
conversion path. New skins need no custom renderer code; they may opt into
`legacy-matte` when a smoother-but-purple-keyed edge is preferable. This is a
universal color-key compatibility policy, not genuine semi-transparency.

## Future true-alpha backend

For non-pixel skins, implement one shared Windows layered-window backend that
composes the entire pet window (sprite plus UI panels) into premultiplied BGRA
and submits it with `UpdateLayeredWindow` / `ULW_ALPHA`. Do not mix that backend
with the current Tk `-transparentcolor` call: Windows documents that after
`SetLayeredWindowAttributes`, `UpdateLayeredWindow` fails until the layered
style is reset. Keep Tk widgets, input, drag, click-through, screen positioning,
panel animation, and DPI behavior under regression tests before switching the
default backend. Then make `spriteEdgeMode` a legacy-only compatibility option
and render the unmodified atlas alpha for every theme.

References: https://learn.microsoft.com/en-us/windows/win32/winmsg/window-features
and https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setlayeredwindowattributes
