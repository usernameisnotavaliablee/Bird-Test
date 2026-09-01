#!/usr/bin/env python3
"""Extract and compare security-relevant Android manifest structure."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET


ANDROID = "{http://schemas.android.com/apk/res/android}"
COMPONENT_TAGS = ("activity", "activity-alias", "service", "receiver", "provider")
COMPONENT_ATTRS = (
    "exported",
    "process",
    "permission",
    "launchMode",
    "windowSoftInputMode",
    "screenOrientation",
    "targetActivity",
)
APP_ATTRS = (
    "name",
    "appComponentFactory",
    "allowBackup",
    "debuggable",
    "extractNativeLibs",
    "networkSecurityConfig",
    "usesCleartextTraffic",
)


def android_attr(node: ET.Element, name: str) -> str | None:
    return node.get(ANDROID + name)


def qualify(package: str, name: str | None) -> str | None:
    if not name:
        return name
    if name.startswith("."):
        return package + name
    if "." not in name:
        return package + "." + name
    return name


def component_key(package: str, tag: str, node: ET.Element) -> str:
    return f"{tag}:{qualify(package, android_attr(node, 'name'))}"


def snapshot(path: Path) -> dict:
    root = ET.parse(path).getroot()
    package = root.get("package", "")
    application = root.find("application")
    if application is None:
        raise ValueError(f"No <application> in {path}")

    components: dict[str, dict[str, str | None]] = {}
    launchers: list[str] = []
    exported: list[str] = []
    for tag in COMPONENT_TAGS:
        for node in application.findall(tag):
            key = component_key(package, tag, node)
            details = {name: android_attr(node, name) for name in COMPONENT_ATTRS}
            components[key] = details
            if details["exported"] == "true":
                exported.append(key)
            for intent_filter in node.findall("intent-filter"):
                actions = {android_attr(x, "name") for x in intent_filter.findall("action")}
                categories = {android_attr(x, "name") for x in intent_filter.findall("category")}
                if (
                    "android.intent.action.MAIN" in actions
                    and "android.intent.category.LAUNCHER" in categories
                ):
                    launchers.append(key)

    sdk = root.find("uses-sdk")
    return {
        "path": str(path),
        "package": package,
        "compile_sdk": android_attr(root, "compileSdkVersion"),
        "min_sdk": android_attr(sdk, "minSdkVersion") if sdk is not None else None,
        "target_sdk": android_attr(sdk, "targetSdkVersion") if sdk is not None else None,
        "application": {name: android_attr(application, name) for name in APP_ATTRS},
        "launchers": sorted(launchers),
        "exported_components": sorted(exported),
        "uses_permissions": sorted(
            {android_attr(node, "name") for node in root.findall("uses-permission") if android_attr(node, "name")}
        ),
        "declared_permissions": sorted(
            {android_attr(node, "name") for node in root.findall("permission") if android_attr(node, "name")}
        ),
        "uses_features": sorted(
            {android_attr(node, "name") for node in root.findall("uses-feature") if android_attr(node, "name")}
        ),
        "query_packages": sorted(
            {
                android_attr(node, "name")
                for queries in root.findall("queries")
                for node in queries.findall("package")
                if android_attr(node, "name")
            }
        ),
        "application_meta_data": sorted(
            {android_attr(node, "name") for node in application.findall("meta-data") if android_attr(node, "name")}
        ),
        "components": components,
    }


def set_delta(left: list[str], right: list[str]) -> dict[str, list[str]]:
    left_set = set(left)
    right_set = set(right)
    return {
        "removed": sorted(left_set - right_set),
        "added": sorted(right_set - left_set),
    }


def compare(left: dict, right: dict) -> dict:
    component_delta = set_delta(list(left["components"]), list(right["components"]))
    common = set(left["components"]) & set(right["components"])
    component_changes = {
        key: {"left": left["components"][key], "right": right["components"][key]}
        for key in sorted(common)
        if left["components"][key] != right["components"][key]
    }
    return {
        "left": left,
        "right": right,
        "delta": {
            "application": {
                key: {"left": left["application"][key], "right": right["application"][key]}
                for key in APP_ATTRS
                if left["application"][key] != right["application"][key]
            },
            "launchers": set_delta(left["launchers"], right["launchers"]),
            "exported_components": set_delta(left["exported_components"], right["exported_components"]),
            "uses_permissions": set_delta(left["uses_permissions"], right["uses_permissions"]),
            "declared_permissions": set_delta(left["declared_permissions"], right["declared_permissions"]),
            "uses_features": set_delta(left["uses_features"], right["uses_features"]),
            "query_packages": set_delta(left["query_packages"], right["query_packages"]),
            "application_meta_data": set_delta(left["application_meta_data"], right["application_meta_data"]),
            "components": component_delta,
            "component_attribute_changes": component_changes,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("left", type=Path)
    parser.add_argument("right", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = compare(snapshot(args.left), snapshot(args.right))
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
