#!/usr/bin/env python3
"""Build the MU Online Blender Tools addon ZIP for Blender installation.

Usage:
    python build_addon.py          # Creates mu_blender_tools.zip
    python build_addon.py output   # Creates output/mu_blender_tools.zip
"""

import os
import shutil
import sys
import tempfile
import zipfile

ADDON_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(ADDON_DIR, "mu_blender_tools")


def build_zip(output_dir: str | None = None) -> str:
    """Create a Blender-installable ZIP of the MU addon.

    The ZIP will have ``__init__.py`` at the root so Blender can
    recognise it directly.

    Args:
        output_dir: Directory to write the ZIP (default: repo root).

    Returns:
        Path to the created ZIP file.
    """
    if output_dir is None:
        output_dir = ADDON_DIR
    os.makedirs(output_dir, exist_ok=True)

    zip_path = os.path.join(output_dir, "mu_blender_tools.zip")

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _dirs, files in os.walk(SOURCE):
            for filename in files:
                if filename.endswith(".pyc"):
                    continue
                full_path = os.path.join(root, filename)
                rel_path = os.path.relpath(full_path, SOURCE)

                # Add to ZIP with ``mu_blender_tools/`` prefix so the
                # folder structure is preserved
                arcname = os.path.join("mu_blender_tools", rel_path)
                zf.write(full_path, arcname)

    return zip_path


def main() -> None:
    output_dir = sys.argv[1] if len(sys.argv) > 1 else None
    zip_path = build_zip(output_dir)
    print(f"✅ Addon package created: {zip_path}")
    print(f"   Size: {os.path.getsize(zip_path) / 1024:.1f} KB")
    print()
    print("📦 Installation instructions:")
    print("   1. Open Blender → Edit → Preferences → Add-ons")
    print("  2. Click 'Install from Disk' (top-right corner)")
    print(f"  3. Select the file: {zip_path}")
    print("  4. Enable 'MU Online Blender Tools' in the list")


if __name__ == "__main__":
    main()
