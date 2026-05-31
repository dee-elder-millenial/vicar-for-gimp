# VICAR for GIMP

**VICAR for GIMP** is a GIMP 3 file loader plug-in for opening NASA/JPL VICAR image files, including many Voyager, planetary science, and PDS archive image products.

If you found an old `.IMG`, `.vic`, or `.vicar` planetary image file and want to open it in GIMP, this plug-in is meant to be the small, practical bridge.

## What it does

The plug-in reads VICAR front labels directly, decodes the image plane to an 8-bit grayscale temporary PGM, and delegates final image creation to GIMP's built-in PNM loader.

It was built while working with Voyager/PDS image data, but it is not Voyager-specific. It is a lightweight image opener, not a replacement for the full NASA-AMMOS/VICAR processing system.

Useful search terms for this project include:

- GIMP VICAR plug-in
- GIMP NASA image opener
- open VICAR image in GIMP
- Voyager image GIMP plug-in
- PDS IMG file viewer
- NASA JPL VICAR image loader
- planetary science image viewer

## Download

The easiest way to download the plug-in is from GitHub:

1. Open this repository on GitHub.
2. Click **Code**.
3. Click **Download ZIP**.
4. Unzip the downloaded file.
5. Copy the `file-vicar` folder into your GIMP 3 plug-ins directory.

You can also clone it with Git:

```bash
git clone https://github.com/dee-elder-millenial/vicar-for-gimp.git
```

## Install

Copy the entire plug-in folder:

```text
file-vicar
```

to your GIMP 3 user plug-ins directory.

On Windows this is usually:

```text
%APPDATA%\GIMP\3.0\plug-ins\file-vicar\file-vicar.py
```

The final layout should look like this:

```text
%APPDATA%\GIMP\3.0\plug-ins\file-vicar\file-vicar.py
```

Then fully restart GIMP.

## Use

Open a VICAR file with:

```text
File > Open
```

or use your operating system's **Open with** action and choose GIMP.

The loader registers:

- Extensions: `.vic`, `.vicar`
- Magic: files beginning with `LBLSIZE=`

Some VICAR files also use `.IMG`. GIMP may still be able to open those when the file begins with a VICAR `LBLSIZE=` label, but `.IMG` is a broad extension used by many unrelated formats, so this plug-in does not claim every `.IMG` file.

It intentionally does not register a thumbnail loader. That keeps GIMP's file chooser from trying to render previews while browsing folders containing many large planetary image files.

## Supported VICAR data

Currently supported:

- VICAR front labels beginning with `LBLSIZE`
- `FORMAT=BYTE`, displayed directly as grayscale
- `FORMAT=HALF`, `FULL`, `REAL`, and `DOUB`, scaled to 8-bit grayscale
- `ORG=BSQ` and common grayscale `ORG=BIL` cases
- Binary headers/prefixes via `NLB` and `NBB`

Not currently supported:

- Full color/multiband rendering
- Advanced VICAR processing operations
- The full NASA-AMMOS/VICAR command ecosystem
- Thumbnail generation inside GIMP's file chooser

## Debugging

If GIMP reports that the VICAR plug-in could not open an image, details are appended to:

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

## Format reference

The implementation follows the VICAR file layout described by the NASA-AMMOS VICAR documentation and is designed to interoperate with files produced for NASA/JPL planetary data archives.

- NASA-AMMOS/VICAR: https://github.com/NASA-AMMOS/VICAR
- VICAR documentation: https://nasa-ammos.github.io/VICAR-DOCS/

## Project status

Early, useful, and intentionally small. Bug reports and test files are welcome, especially for real-world planetary image products that do not open correctly yet.

## License

This project is licensed under GPL-3.0-or-later. See `LICENSE`.

This is an unofficial project. It is not endorsed by NASA, JPL, Caltech, the NASA-AMMOS/VICAR project, or the GIMP project.
