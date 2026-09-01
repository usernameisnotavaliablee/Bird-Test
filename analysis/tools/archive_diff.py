#!/usr/bin/env python3
"""Compare APK/ZIP entry inventories by name, size and CRC32."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from zipfile import ZipFile


def inventory(path: Path) -> dict[str, dict[str, int]]:
    with ZipFile(path) as archive:
        return {
            info.filename: {
                "size": info.file_size,
                "compressed_size": info.compress_size,
                "crc32": info.CRC,
                "compression": info.compress_type,
            }
            for info in archive.infolist()
        }


def compare(left_path: Path, right_path: Path) -> dict:
    left = inventory(left_path)
    right = inventory(right_path)
    left_names = set(left)
    right_names = set(right)
    common = left_names & right_names
    changed = {
        name: {"left": left[name], "right": right[name]}
        for name in sorted(common)
        if (left[name]["size"], left[name]["crc32"])
        != (right[name]["size"], right[name]["crc32"])
    }
    unchanged = common - set(changed)
    return {
        "left": str(left_path),
        "right": str(right_path),
        "counts": {
            "left_entries": len(left),
            "right_entries": len(right),
            "added": len(right_names - left_names),
            "removed": len(left_names - right_names),
            "changed_content": len(changed),
            "unchanged_content": len(unchanged),
        },
        "added": sorted(right_names - left_names),
        "removed": sorted(left_names - right_names),
        "changed": changed,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("left", type=Path)
    parser.add_argument("right", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    rendered = json.dumps(compare(args.left, args.right), ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
