#!/usr/bin/env python3
"""
画像ファイルの内部を徹底チェックし、壊れているものを再ダウンロード
- fileコマンドでJPEGと判定されても、内部にUTF-8置換文字(efbfbd)が含まれていれば壊れている
"""

import subprocess
import json
import time
import random
import urllib.request
import urllib.parse
from pathlib import Path

ANKI_DIR = Path(__file__).parent
IMAGES_DIR = Path.home() / "Documents/private_matters/20260115plants_images"
IMAGE_LIST = ANKI_DIR / "image_list.json"
PART2_DIR = ANKI_DIR.parent / "Part2"
import re

TIMEOUT = 30

def is_truly_valid_image(filepath):
    """画像が本当に正常かチェック（内部にefbfbdがないか確認）"""
    with open(filepath, 'rb') as f:
        data = f.read()

    # UTF-8置換文字のパターンが含まれていたら壊れている
    # efbfbd が連続して出現するパターンを検出
    corruption_pattern = b'\xef\xbf\xbd'

    # 最初の1000バイトに壊れたパターンがあるかチェック
    if corruption_pattern in data[:1000]:
        return False

    # さらに、正常なJPEGの構造かチェック
    if filepath.suffix.lower() in ['.jpg', '.jpeg']:
        # JPEGは FF D8 FF で始まる
        if not data.startswith(b'\xff\xd8\xff'):
            return False

    return True

def get_scientific_name_from_part2(plant_name):
    """Part2ファイルから学名を取得"""
    for md_file in PART2_DIR.glob("*.md"):
        content = md_file.read_text(encoding='utf-8')
        # 植物名を含む行を検索
        pattern = rf'\[{re.escape(plant_name)}\].*?\*([A-Z][a-z]+(?:\s+[a-z]+)?)\*'
        match = re.search(pattern, content)
        if match:
            return match.group(1)
    return None

def get_inaturalist_image(scientific_name):
    """iNaturalist APIから画像URLを取得"""
    api_url = f"https://api.inaturalist.org/v1/taxa/autocomplete?q={urllib.parse.quote(scientific_name)}&rank=species"

    try:
        req = urllib.request.Request(api_url, headers={
            "User-Agent": "PlantStudyApp/1.0 (educational use)",
            "Accept": "application/json"
        })
        with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
            data = json.loads(response.read().decode('utf-8'))

            results = data.get('results', [])
            if results:
                taxon = results[0]
                default_photo = taxon.get('default_photo')
                if default_photo:
                    medium_url = default_photo.get('medium_url')
                    if medium_url:
                        return medium_url
    except Exception as e:
        print(f"  API Error: {e}")
    return None

def download_image(url, filepath):
    """画像をダウンロード"""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "PlantStudyApp/1.0 (educational use)",
            "Accept": "image/*"
        })
        with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
            data = response.read()
            if len(data) > 1024:
                with open(filepath, 'wb') as f:
                    f.write(data)
                return True
    except Exception as e:
        print(f"  Download error: {e}")
    return False

def main():
    print("=== 画像の徹底チェック開始 ===\n")

    # 全画像をチェック
    corrupted = []
    for f in sorted(IMAGES_DIR.glob("*")):
        if f.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif']:
            if not is_truly_valid_image(f):
                plant_name = f.stem
                corrupted.append((plant_name, f))
                print(f"壊れている: {f.name}")

    print(f"\n壊れた画像: {len(corrupted)}件\n")

    if not corrupted:
        print("全ての画像が正常です")
        return

    # 壊れた画像を再ダウンロード
    success = 0
    failed = []

    for plant_name, filepath in corrupted:
        print(f"\n処理中: {plant_name}")

        # 学名を取得
        scientific_name = get_scientific_name_from_part2(plant_name)
        if not scientific_name:
            print(f"  学名が見つからない")
            failed.append(plant_name)
            continue

        print(f"  学名: {scientific_name}")

        # 古いファイルを削除
        filepath.unlink()

        # iNaturalistから画像URLを取得
        image_url = get_inaturalist_image(scientific_name)
        if not image_url:
            print(f"  画像URLが見つからない")
            failed.append(plant_name)
            continue

        # ダウンロード
        time.sleep(random.uniform(0.5, 1.0))
        new_filepath = IMAGES_DIR / f"{plant_name}.jpg"

        if download_image(image_url, new_filepath):
            # 再度検証
            if is_truly_valid_image(new_filepath):
                print(f"  成功: {new_filepath.name}")
                success += 1
            else:
                print(f"  再ダウンロードも壊れている")
                new_filepath.unlink()
                failed.append(plant_name)
        else:
            failed.append(plant_name)

        time.sleep(random.uniform(1.0, 2.0))

    print(f"\n=== 完了 ===")
    print(f"修復成功: {success}件")
    print(f"修復失敗: {len(failed)}件")
    if failed:
        print(f"失敗リスト: {failed}")

if __name__ == "__main__":
    main()
