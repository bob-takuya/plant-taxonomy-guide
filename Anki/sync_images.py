#!/usr/bin/env python3
"""
imagesフォルダの画像とimage_list.jsonを同期
"""

import json
import os
from pathlib import Path

ANKI_DIR = Path(__file__).parent
IMAGES_DIR = Path.home() / "Documents/private_matters/20260115plants_images"
OUTPUT_JSON = ANKI_DIR / "image_list.json"

def main():
    # 既存のJSONを読み込み
    existing = {}
    if OUTPUT_JSON.exists():
        with open(OUTPUT_JSON, 'r', encoding='utf-8') as f:
            data = json.load(f)
            existing = {item['filename']: item for item in data}

    # imagesフォルダをスキャン
    image_data = []
    for img_file in sorted(IMAGES_DIR.glob("*")):
        if img_file.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
            filename = img_file.name
            name = img_file.stem

            if filename in existing:
                image_data.append(existing[filename])
            else:
                image_data.append({
                    "name": name,
                    "wikipedia_title": name,
                    "filename": filename,
                    "size": img_file.stat().st_size
                })

    # 保存
    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(image_data, f, ensure_ascii=False, indent=2)

    print(f"Synced: {len(image_data)} images")

if __name__ == "__main__":
    main()