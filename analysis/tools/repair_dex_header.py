#!/usr/bin/env python3
"""Repair the SHA-1 signature and Adler-32 checksum in a copied DEX file."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import struct
import zlib


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument(
        "--zero-map-list",
        action="store_true",
        help="Replace an intentionally corrupted map-list count with zero.",
    )
    args = parser.parse_args()

    data = bytearray(args.source.read_bytes())
    if len(data) < 32 or not data.startswith(b"dex\n"):
        raise ValueError(f"Not a DEX file: {args.source}")

    if args.zero_map_list:
        map_offset = struct.unpack("<I", data[52:56])[0]
        if map_offset <= 0 or map_offset + 4 > len(data):
            raise ValueError(f"Invalid map offset {map_offset} in {args.source}")
        data[map_offset : map_offset + 4] = b"\x00\x00\x00\x00"

    data[12:32] = hashlib.sha1(data[32:]).digest()
    data[8:12] = struct.pack("<I", zlib.adler32(data[12:]) & 0xFFFFFFFF)
    args.destination.parent.mkdir(parents=True, exist_ok=True)
    args.destination.write_bytes(data)


if __name__ == "__main__":
    main()
