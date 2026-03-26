#!/usr/bin/env python3
"""壊れた画像を検出して削除"""
import subprocess
from pathlib import Path

IMAGES_DIR = Path.home() / "Documents/private_matters/20260115plants_images"

corrupted = []
for f in IMAGES_DIR.glob("*"):
    if f.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif']:
        result = subprocess.run(['file', '-b', str(f)], capture_output=True)
        ftype = result.stdout.decode('utf-8', errors='ignore').strip()
        if not any(x in ftype for x in ['JPEG', 'PNG', 'GIF', 'image']):
            corrupted.append(f.name)
            print(f"Corrupted: {f.name} - {ftype}")

print(f"\nTotal corrupted: {len(corrupted)}")

# 壊れた画像を削除
if corrupted:
    print("\nDeleting corrupted images...")
    for name in corrupted:
        (IMAGES_DIR / name).unlink()
        print(f"  Deleted: {name}")
