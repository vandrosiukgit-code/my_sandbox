"""Prune card resources below six and jokers from assets/resource_manifest.json."""

from __future__ import annotations

import json
import os
import sys


PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST_PATH = os.path.join(PROJECT_DIR, "assets", "resource_manifest.json")
REMOVED_RANK_PREFIXES = ("cards.2_of_", "cards.3_of_", "cards.4_of_", "cards.5_of_")


def should_remove_resource(resource_key):
    if not isinstance(resource_key, str):
        return False
    if resource_key.lower().startswith(REMOVED_RANK_PREFIXES):
        return True
    return "joker" in resource_key.lower()


def prune_manifest(path):
    with open(path, "r", encoding="utf-8") as manifest_file:
        manifest = json.load(manifest_file)

    resources = dict(manifest.get("resources", {}))
    removed_keys = [
        resource_key
        for resource_key in resources
        if should_remove_resource(resource_key)
    ]
    for resource_key in removed_keys:
        resources.pop(resource_key, None)

    manifest["resources"] = dict(sorted(resources.items()))

    with open(path, "w", encoding="utf-8") as manifest_file:
        json.dump(manifest, manifest_file, ensure_ascii=True, indent=2)
        manifest_file.write("\n")

    return removed_keys


def main():
    removed_keys = prune_manifest(MANIFEST_PATH)
    print(f"Manifest: {MANIFEST_PATH}")
    print(f"Removed resources: {len(removed_keys)}")
    for resource_key in removed_keys:
        print(resource_key)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
