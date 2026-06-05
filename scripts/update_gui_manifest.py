"""Regenerate assets/gui_manifest.json from the current TableScreen layout."""

from __future__ import annotations

import os
import sys


PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS_DIR = os.path.join(PROJECT_DIR, "assets")

if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

from tools.resource_picker import ResourcePickerService  # noqa: E402


def main():
    service = ResourcePickerService(PROJECT_DIR, ASSETS_DIR)
    manifest, report = service.update_gui_manifest()
    service.save_gui_manifest(manifest)
    print(report.to_text())


if __name__ == "__main__":
    main()
