#!/usr/bin/env python3
"""
iNaturalist APIを使って植物画像をダウンロード
Wikimedia Commonsよりレート制限が緩い
"""

import sys
import os
import re
import json
import time
import urllib.request
import urllib.parse
import urllib.error
import random
from pathlib import Path

# 出力をバッファリングしない
sys.stdout.reconfigure(line_buffering=True)
print("iNaturalist画像ダウンロードスクリプト開始...", flush=True)

# 設定
PART2_DIR = Path(__file__).parent.parent / "Part2"
IMAGES_DIR = Path.home() / "Documents/private_matters/20260115plants_images"
OUTPUT_JSON = Path(__file__).parent / "image_list.json"
FAILED_JSON = Path(__file__).parent / "failed_inaturalist.json"

# レート制限設定（iNaturalistは比較的緩い）
DELAY_MIN = 1.0  # 最小待機時間
DELAY_MAX = 2.0  # 最大待機時間
MAX_RETRIES = 3
TIMEOUT = 30

def extract_species_from_markdown(md_content):
    """Markdownから学名と和名のペアを抽出"""
    species = []

    # パターン1: | [和名](URL) | *学名* | ... | のテーブル形式
    # 例: | [アカマツ](https://ja.wikipedia.org/wiki/アカマツ) | *Pinus densiflora* |
    pattern1 = r'\|\s*\[([^\]]+)\]\([^)]+\)\s*\|\s*\*([A-Z][a-z]+\s+[a-z]+(?:\s+var\.\s+[a-z]+)?)\*'
    matches1 = re.findall(pattern1, md_content)
    for name, scientific in matches1:
        # 学名からvar.部分を除去（基本種名で検索するため）
        base_scientific = re.sub(r'\s+var\.\s+[a-z]+', '', scientific)
        species.append((name.strip(), base_scientific.strip()))

    # パターン2: **和名**（*学名*）の形式
    pattern2 = r'\*\*([^*]+)\*\*[（(]\*([A-Z][a-z]+\s+[a-z]+)\*[）)]'
    matches2 = re.findall(pattern2, md_content)
    for name, scientific in matches2:
        species.append((name.strip(), scientific.strip()))

    return species

def get_inaturalist_image(scientific_name, retries=0):
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
                # 最初の結果からdefault_photoを取得
                taxon = results[0]
                default_photo = taxon.get('default_photo')
                if default_photo:
                    # medium_urlを使用（適切なサイズ）
                    medium_url = default_photo.get('medium_url')
                    if medium_url:
                        return {
                            'url': medium_url,
                            'attribution': default_photo.get('attribution', ''),
                            'license': default_photo.get('license_code', ''),
                            'taxon_name': taxon.get('name', ''),
                            'common_name': taxon.get('preferred_common_name', '')
                        }
    except urllib.error.HTTPError as e:
        if e.code == 429 and retries < MAX_RETRIES:
            wait_time = 30 * (retries + 1)
            print(f"  Rate limited, waiting {wait_time}s...")
            time.sleep(wait_time)
            return get_inaturalist_image(scientific_name, retries + 1)
        print(f"  HTTP Error {e.code}")
    except Exception as e:
        print(f"  Error: {e}")

    return None

def is_valid_image(filepath):
    """画像ファイルが正常かどうかを検証"""
    import subprocess
    try:
        result = subprocess.run(['file', '-b', str(filepath)], capture_output=True)
        ftype = result.stdout.decode('utf-8', errors='ignore').strip()
        return any(x in ftype for x in ['JPEG', 'PNG', 'GIF', 'image'])
    except:
        return False

def download_image(url, filepath, retries=0):
    """画像をダウンロードし、正常な画像か検証"""
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
                # 画像が正常か検証
                if is_valid_image(filepath):
                    return True, len(data)
                else:
                    print(f"  Invalid image format, deleting...")
                    filepath.unlink()
                    return False, 0
    except urllib.error.HTTPError as e:
        if e.code == 429 and retries < MAX_RETRIES:
            wait_time = 30 * (retries + 1)
            print(f"  Download rate limited, waiting {wait_time}s...")
            time.sleep(wait_time)
            return download_image(url, filepath, retries + 1)
        print(f"  Download HTTP Error {e.code}")
    except Exception as e:
        print(f"  Download error: {e}")
    return False, 0

def sanitize_filename(name):
    """ファイル名として安全な文字列に変換"""
    invalid_chars = r'[<>:"/\\|?*\x00-\x1f]'
    name = re.sub(invalid_chars, '', name)
    return name[:80]

def get_extension_from_url(url):
    """URLから拡張子を取得"""
    parsed = urllib.parse.urlparse(url)
    path = parsed.path.lower()
    for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
        if ext in path:
            return ext if ext != '.jpeg' else '.jpg'
    return '.jpg'

def load_existing_data():
    """既存データを読み込み"""
    if OUTPUT_JSON.exists():
        with open(OUTPUT_JSON, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def main():
    IMAGES_DIR.mkdir(exist_ok=True)

    # 既存データをロード
    existing_data = load_existing_data()
    existing_names = {item['name'] for item in existing_data}

    print(f"既存画像数: {len(existing_names)}")

    # 全Part2ファイルから種名を抽出
    all_species = {}

    for md_file in sorted(PART2_DIR.glob("*.md")):
        content = md_file.read_text(encoding='utf-8')
        species_list = extract_species_from_markdown(content)

        for name, scientific in species_list:
            # 除外キーワード
            exclude_keywords = ['科', '目', '門', '綱', '属', '類', '群', '植物',
                              '分類', '形態', '概論', '体系', '進化', '系統']
            if not any(kw in name for kw in exclude_keywords) and len(name) >= 2:
                if name not in all_species:
                    all_species[name] = scientific

    # 未ダウンロードのみ処理
    to_download = {k: v for k, v in all_species.items() if k not in existing_names}

    print(f"\n抽出した種数: {len(all_species)}")
    print(f"ダウンロード対象: {len(to_download)}")

    if len(to_download) == 0:
        print("\n新規ダウンロード対象がありません。")
        return

    image_data = existing_data.copy()
    failed_list = []
    success_count = 0
    fail_count = 0

    for i, (name, scientific) in enumerate(sorted(to_download.items())):
        print(f"[{i+1}/{len(to_download)}] {name} ({scientific})...")

        # iNaturalistから画像情報を取得
        image_info = get_inaturalist_image(scientific)

        if image_info:
            image_url = image_info['url']
            ext = get_extension_from_url(image_url)
            filename = f"{sanitize_filename(name)}{ext}"
            filepath = IMAGES_DIR / filename

            if filepath.exists() and filepath.stat().st_size > 1024:
                print(f"  既存: {filename}")
                image_data.append({
                    "name": name,
                    "scientific_name": scientific,
                    "filename": filename,
                    "url": image_url,
                    "source": "iNaturalist",
                    "attribution": image_info['attribution'],
                    "size": filepath.stat().st_size
                })
                success_count += 1
            else:
                # 少し待機してからダウンロード
                time.sleep(random.uniform(0.5, 1.0))

                print(f"  ダウンロード中: {filename}")
                success, file_size = download_image(image_url, filepath)

                if success:
                    image_data.append({
                        "name": name,
                        "scientific_name": scientific,
                        "filename": filename,
                        "url": image_url,
                        "source": "iNaturalist",
                        "attribution": image_info['attribution'],
                        "size": file_size
                    })
                    success_count += 1
                    print(f"  OK ({file_size // 1024}KB)")
                else:
                    failed_list.append({"name": name, "scientific_name": scientific})
                    fail_count += 1
                    print(f"  FAILED")
        else:
            print(f"  画像なし")
            failed_list.append({"name": name, "scientific_name": scientific})
            fail_count += 1

        # 待機
        time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

        # 進捗保存（50件ごと）
        if (i + 1) % 50 == 0:
            with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
                json.dump(image_data, f, ensure_ascii=False, indent=2)
            print(f"  [保存: {len(image_data)} images, 新規{success_count}, 失敗{fail_count}]")

    # 最終保存
    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(image_data, f, ensure_ascii=False, indent=2)

    with open(FAILED_JSON, 'w', encoding='utf-8') as f:
        json.dump(failed_list, f, ensure_ascii=False, indent=2)

    print(f"\n=== 完了 ===")
    print(f"成功: {success_count}")
    print(f"失敗: {fail_count}")
    print(f"合計画像数: {len(image_data)}")

if __name__ == "__main__":
    main()