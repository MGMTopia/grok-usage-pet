# Third-party notices

Grok Usage Pet includes or is packaged with third-party software. Those
components retain their own licenses; the project MIT license does not replace
them.

| Component | Release build | License copy in the Windows archive |
|---|---:|---|
| CPython | Latest Python 3.12 patch selected by `actions/setup-python` | `THIRD_PARTY_LICENSES/PYTHON_LICENSE.txt` |
| Tcl/Tk | Version bundled with that CPython build | `THIRD_PARTY_LICENSES/TCL_TK_LICENSE.txt` |
| Pillow and its bundled image libraries | 12.3.0 | `THIRD_PARTY_LICENSES/PILLOW_LICENSE.txt` |
| PyInstaller bootloader and runtime hooks | 6.22.2 | `THIRD_PARTY_LICENSES/PYINSTALLER_COPYING.txt` |

The Pillow license copy also contains notices for native libraries included in
the official Pillow wheel, such as Brotli, FreeType, libjpeg-turbo, Little CMS,
libpng, libwebp, OpenJPEG, LibTIFF, XZ, and zlib-ng when present in that wheel.

Project source and release scripts:

- CPython: https://github.com/python/cpython
- Tcl/Tk: https://www.tcl.tk/
- Pillow: https://github.com/python-pillow/Pillow
- PyInstaller: https://github.com/pyinstaller/pyinstaller

The complete license files are copied from the exact Python environment used
to build each Windows archive. If a required license cannot be located, the
release script stops rather than publishing an incomplete package.
