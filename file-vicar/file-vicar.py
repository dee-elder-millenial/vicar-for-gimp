#!/usr/bin/env python3
"""GIMP 3 loader for VICAR image files.

The loader is intentionally self-contained so it can run inside GIMP's bundled
Python on Windows. It implements the core VICAR image layout described by the
NASA-AMMOS VICAR file format documentation: front labels beginning with
LBLSIZE, followed by optional binary header records and fixed-size image
records.
"""

from __future__ import annotations

import math
import os
import re
import struct
import sys
import tempfile
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class VicarError(RuntimeError):
    pass


@dataclass
class VicarImage:
    path: Path
    labels: dict[str, Any]
    width: int
    height: int
    bands: int
    pixels_u8: bytes


def _strip_label_value(value: str) -> Any:
    value = value.strip().rstrip("\x00")
    if len(value) >= 2 and value[0] == "'" and value[-1] == "'":
        return value[1:-1].replace("''", "'")
    if len(value) >= 2 and value[0] == "(" and value[-1] == ")":
        return [_strip_label_value(part) for part in _split_tuple(value[1:-1])]
    if re.fullmatch(r"[+-]?\d+", value):
        try:
            return int(value)
        except ValueError:
            pass
    if re.fullmatch(r"[+-]?(\d+(\.\d*)?|\.\d+)([EeDd][+-]?\d+)?", value):
        try:
            return float(value.replace("D", "E").replace("d", "e"))
        except ValueError:
            pass
    return value


def _split_tuple(text: str) -> list[str]:
    parts: list[str] = []
    start = 0
    in_quote = False
    index = 0
    while index < len(text):
        char = text[index]
        if char == "'":
            if in_quote and index + 1 < len(text) and text[index + 1] == "'":
                index += 2
                continue
            in_quote = not in_quote
        elif char == "," and not in_quote:
            parts.append(text[start:index].strip())
            start = index + 1
        index += 1
    parts.append(text[start:].strip())
    return parts


def parse_vicar_label(label_text: str) -> dict[str, Any]:
    labels: dict[str, Any] = {}
    index = 0
    length = len(label_text)
    while index < length:
        while index < length and label_text[index].isspace():
            index += 1
        if index >= length or label_text[index] == "\x00":
            break

        key_start = index
        while index < length and (label_text[index].isalnum() or label_text[index] == "_"):
            index += 1
        key = label_text[key_start:index]
        if not key:
            index += 1
            continue
        while index < length and label_text[index].isspace():
            index += 1
        if index >= length or label_text[index] != "=":
            continue
        index += 1
        while index < length and label_text[index].isspace():
            index += 1

        value_start = index
        if index < length and label_text[index] == "'":
            index += 1
            while index < length:
                if label_text[index] == "'":
                    if index + 1 < length and label_text[index + 1] == "'":
                        index += 2
                        continue
                    index += 1
                    break
                index += 1
        elif index < length and label_text[index] == "(":
            depth = 1
            in_quote = False
            index += 1
            while index < length and depth:
                char = label_text[index]
                if char == "'":
                    if in_quote and index + 1 < length and label_text[index + 1] == "'":
                        index += 2
                        continue
                    in_quote = not in_quote
                elif not in_quote:
                    if char == "(":
                        depth += 1
                    elif char == ")":
                        depth -= 1
                index += 1
        else:
            while index < length and not label_text[index].isspace() and label_text[index] != "\x00":
                index += 1

        labels[key] = _strip_label_value(label_text[value_start:index])
    return labels


def read_vicar_labels(path: Path) -> tuple[dict[str, Any], bytes]:
    with path.open("rb") as handle:
        prefix = handle.read(256)
        match = re.match(rb"\s*LBLSIZE\s*=\s*(\d+)", prefix)
        if not match:
            raise VicarError("Not a VICAR file: missing leading LBLSIZE label")
        lblsize = int(match.group(1))
        handle.seek(0)
        label_bytes = handle.read(lblsize)
    label_text = label_bytes.split(b"\x00", 1)[0].decode("ascii", errors="replace")
    labels = parse_vicar_label(label_text)
    if "LBLSIZE" not in labels:
        labels["LBLSIZE"] = lblsize
    return labels, label_bytes


def _int_label(labels: dict[str, Any], name: str, default: int = 0) -> int:
    value = labels.get(name, default)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _str_label(labels: dict[str, Any], name: str, default: str = "") -> str:
    value = labels.get(name, default)
    return str(value).strip().upper()


def _pixel_info(labels: dict[str, Any]) -> tuple[str, int, str]:
    fmt = _str_label(labels, "FORMAT", "BYTE")
    intfmt = _str_label(labels, "INTFMT", "LOW")
    realfmt = _str_label(labels, "REALFMT", "RIEEE")
    endian_int = ">" if intfmt == "HIGH" else "<"
    endian_real = ">" if realfmt == "IEEE" else "<"
    if fmt in {"BYTE"}:
        return "B", 1, ""
    if fmt in {"HALF", "WORD"}:
        return "h", 2, endian_int
    if fmt in {"FULL", "LONG"}:
        return "i", 4, endian_int
    if fmt == "REAL":
        return "f", 4, endian_real
    if fmt == "DOUB":
        return "d", 8, endian_real
    raise VicarError(f"Unsupported VICAR FORMAT={fmt!r}")


def _scale_to_u8(values: list[float]) -> bytes:
    finite = [value for value in values if math.isfinite(value)]
    if not finite:
        return bytes(len(values))
    low = min(finite)
    high = max(finite)
    if high <= low:
        return bytes(0 if value <= low else 255 for value in values)
    scale = 255.0 / (high - low)
    return bytes(max(0, min(255, int(round((value - low) * scale)))) if math.isfinite(value) else 0 for value in values)


def _read_record(handle, offset: int, record_size: int, nbb: int, payload_bytes: int) -> bytes:
    handle.seek(offset + nbb)
    data = handle.read(payload_bytes)
    if len(data) != payload_bytes:
        raise VicarError("Unexpected end of file while reading image data")
    return data


def load_vicar_pixels(path: Path) -> VicarImage:
    labels, _label_bytes = read_vicar_labels(path)
    lblsize = _int_label(labels, "LBLSIZE")
    recsize = _int_label(labels, "RECSIZE")
    nlb = _int_label(labels, "NLB")
    nbb = _int_label(labels, "NBB")
    org = _str_label(labels, "ORG", "BSQ")
    ns = _int_label(labels, "NS")
    nl = _int_label(labels, "NL")
    nb = max(1, _int_label(labels, "NB", 1))
    n1 = _int_label(labels, "N1", ns if org in {"BSQ", "BIL"} else nb)
    n2 = _int_label(labels, "N2", nl if org == "BSQ" else (nb if org == "BIL" else ns))
    _n3 = _int_label(labels, "N3", nb if org == "BSQ" else nl)

    code, pixel_size, endian = _pixel_info(labels)
    if not ns or not nl or not recsize:
        raise VicarError("VICAR file is missing NS, NL, or RECSIZE")

    image_offset = lblsize + nlb * recsize
    payload_bytes = n1 * pixel_size
    pixels: bytes | list[float]

    with path.open("rb") as handle:
        if code == "B":
            out = bytearray(ns * nl)
            if org == "BSQ":
                for y in range(nl):
                    record_index = y
                    record = _read_record(handle, image_offset + record_index * recsize, recsize, nbb, payload_bytes)
                    out[y * ns:(y + 1) * ns] = record[:ns]
            elif org == "BIL":
                for y in range(nl):
                    record_index = y * nb
                    record = _read_record(handle, image_offset + record_index * recsize, recsize, nbb, payload_bytes)
                    out[y * ns:(y + 1) * ns] = record[:ns]
            elif org == "BIP":
                for y in range(nl):
                    for x in range(ns):
                        record_index = y * ns + x
                        record = _read_record(handle, image_offset + record_index * recsize, recsize, nbb, payload_bytes)
                        out[y * ns + x] = record[0]
            else:
                raise VicarError(f"Unsupported VICAR ORG={org!r}")
            pixels = bytes(out)
        else:
            unpack_one = struct.Struct(endian + code).unpack
            values: list[float] = []
            if org == "BSQ":
                record_indexes = range(nl)
            elif org == "BIL":
                record_indexes = (y * nb for y in range(nl))
            else:
                raise VicarError(f"Unsupported non-BYTE VICAR ORG={org!r}")
            for record_index in record_indexes:
                record = _read_record(handle, image_offset + record_index * recsize, recsize, nbb, payload_bytes)
                for start in range(0, ns * pixel_size, pixel_size):
                    values.append(float(unpack_one(record[start:start + pixel_size])[0]))
            pixels = _scale_to_u8(values)

    return VicarImage(path=path, labels=labels, width=ns, height=nl, bands=nb, pixels_u8=pixels)


def _write_pgm(vicar_path: Path, pgm_path: Path) -> None:
    image = load_vicar_pixels(vicar_path)
    with pgm_path.open("wb") as handle:
        handle.write(f"P5\n{image.width} {image.height}\n255\n".encode("ascii"))
        handle.write(image.pixels_u8)


def _standalone_main(argv: list[str]) -> int:
    if len(argv) >= 3 and argv[1] == "--dump-info":
        image = load_vicar_pixels(Path(argv[2]))
        for key in ("FORMAT", "ORG", "NL", "NS", "NB", "NBB", "NLB", "RECSIZE", "INTFMT", "REALFMT"):
            print(f"{key}={image.labels.get(key)}")
        print(f"width={image.width} height={image.height} bytes={len(image.pixels_u8)}")
        return 0
    if len(argv) >= 4 and argv[1] == "--write-pgm":
        _write_pgm(Path(argv[2]), Path(argv[3]))
        return 0
    return 2


if len(sys.argv) > 1 and sys.argv[1] in {"--dump-info", "--write-pgm"}:
    raise SystemExit(_standalone_main(sys.argv))


import gi

gi.require_version("Gimp", "3.0")
from gi.repository import Gimp

gi.require_version("Gegl", "0.4")
from gi.repository import Gegl

from gi.repository import Gio, GLib, GObject


def _log_exception(exc: Exception) -> None:
    try:
        log_path = Path.home() / "AppData" / "Roaming" / "GIMP" / "3.0" / "file-vicar.log"
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write("\n--- VICAR loader error ---\n")
            handle.write(f"{exc!r}\n")
            handle.write(traceback.format_exc())
    except Exception:
        pass


def _log_event(message: str) -> None:
    try:
        log_path = Path.home() / "AppData" / "Roaming" / "GIMP" / "3.0" / "file-vicar.log"
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"\n--- VICAR loader event ---\n{message}\n")
    except Exception:
        pass


def _error_return(procedure, message: str):
    return procedure.new_return_values(Gimp.PDBStatusType.EXECUTION_ERROR, GLib.Error(message))


def load_vicar(procedure, run_mode, file, metadata, flags, config, data):
    tmp_name = None
    try:
        path = Path(file.peek_path())
        _log_event(f"load_vicar entered for {path}")
        Gimp.progress_init("Loading VICAR image")
        with tempfile.NamedTemporaryFile(prefix="gimp-vicar-", suffix=".pgm", delete=False) as tmp:
            tmp_name = tmp.name
            parsed = load_vicar_pixels(path)
            _log_event(f"decoded {path.name}: {parsed.width}x{parsed.height}, writing {tmp_name}")
            tmp.write(f"P5\n{parsed.width} {parsed.height}\n255\n".encode("ascii"))
            tmp.write(parsed.pixels_u8)

        pdb_proc = Gimp.get_pdb().lookup_procedure("file-pnm-load")
        if pdb_proc is None:
            raise VicarError("GIMP procedure file-pnm-load was not found")
        pdb_config = pdb_proc.create_config()
        pdb_config.set_property("run-mode", Gimp.RunMode.NONINTERACTIVE)
        pdb_config.set_property("file", Gio.File.new_for_path(tmp_name))
        result = pdb_proc.run(pdb_config)
        _log_event(f"file-pnm-load returned {result.index(0)}")
        if int(result.index(0)) != int(Gimp.PDBStatusType.SUCCESS):
            raise VicarError(str(result.index(1)))

        image = result.index(1)
        try:
            image.set_file(file)
        except Exception as exc:
            _log_event(f"image.set_file failed but image loaded: {exc!r}")
        return Gimp.ValueArray.new_from_values([
            GObject.Value(Gimp.PDBStatusType, Gimp.PDBStatusType.SUCCESS),
            GObject.Value(Gimp.Image, image),
        ]), flags
    except Exception as exc:
        _log_exception(exc)
        return _error_return(procedure, str(exc)), flags
    finally:
        if tmp_name:
            try:
                os.remove(tmp_name)
            except OSError:
                pass


class FileVicar(Gimp.PlugIn):
    def do_query_procedures(self):
        return ["file-vicar-load"]

    def do_create_procedure(self, name):
        if name == "file-vicar-load":
            procedure = Gimp.LoadProcedure.new(self, name, Gimp.PDBProcType.PLUGIN, load_vicar, None)
            procedure.set_menu_label("VICAR")
            procedure.set_documentation("Load a VICAR image", "Load NASA/JPL VICAR image files.", name)
            procedure.set_extensions("vic,vicar")
            procedure.set_mime_types("image/x-vicar")
            procedure.set_magics("0,string,LBLSIZE=")
        else:
            return None
        procedure.set_attribution("OpenAI Codex", "OpenAI Codex", "2026")
        return procedure


Gimp.main(FileVicar.__gtype__, sys.argv)
