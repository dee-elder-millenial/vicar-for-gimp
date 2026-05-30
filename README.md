# vicar-for-gimp

GIMP 3 file loader plug-in for opening NASA/JPL VICAR image files.

The plug-in was built while working with Voyager/PDS image data, but it is not
Voyager-specific. It reads VICAR labels directly, decodes the image plane to an
8-bit grayscale temporary PGM, and delegates final image creation to GIMP's
built-in PNM loader.

## Install

Copy the plug-in folder:

```text
file-vicar
```

to your GIMP 3 user plug-ins directory.

On Windows this is usually:

```text
%APPDATA%\GIMP\3.0\plug-ins\file-vicar\file-vicar.py
```

Then fully restart GIMP.

## Use

Open a VICAR file with:

```text
File > Open
```

or use your OS "Open with" action and choose GIMP.

The loader registers:

- Extensions: `.vic`, `.vicar`
- Magic: files beginning with `LBLSIZE=`

It intentionally does not register a thumbnail loader. That keeps GIMP's file
chooser from trying to render previews while browsing folders containing many
large planetary image files.

## Supported

- VICAR front labels beginning with `LBLSIZE`
- `FORMAT=BYTE`, displayed directly as grayscale
- `FORMAT=HALF`, `FULL`, `REAL`, and `DOUB`, scaled to 8-bit grayscale
- `ORG=BSQ` and common grayscale `ORG=BIL` cases
- Binary headers/prefixes via `NLB` and `NBB`

The loader is intentionally small and self-contained. It does not build or
bundle the full NASA-AMMOS/VICAR processing system.

## Debugging

If GIMP reports that the VICAR plug-in could not open an image, details are
appended to:

```text
%APPDATA%\GIMP\3.0\file-vicar.log
```

You can also test the parser from a terminal with GIMP's bundled Python:

```powershell
& "C:\Program Files\GIMP 3\bin\python.exe" file-vicar\file-vicar.py --dump-info "path\to\image.vic"
```

To write a standalone grayscale PGM for inspection:

```powershell
& "C:\Program Files\GIMP 3\bin\python.exe" file-vicar\file-vicar.py --write-pgm "path\to\image.vic" "out.pgm"
```

## Format Reference

The implementation follows the VICAR file layout described by the NASA-AMMOS
VICAR documentation and is designed to interoperate with files produced for
NASA/JPL planetary data archives.

- NASA-AMMOS/VICAR: https://github.com/NASA-AMMOS/VICAR
- VICAR documentation: https://nasa-ammos.github.io/VICAR-DOCS/
