#!/usr/bin/env python3
"""
失敗した種に対して代替名で再検索
"""

import json
import time
import urllib.request
import urllib.parse
import urllib.error
import random
import subprocess
from pathlib import Path

ANKI_DIR = Path(__file__).parent
IMAGES_DIR = Path.home() / "Documents/private_matters/20260115plants_images"
IMAGE_LIST = ANKI_DIR / "image_list.json"
FAILED_JSON = ANKI_DIR / "failed_inaturalist.json"

# 代替検索名のマッピング
ALTERNATIVE_NAMES = {
    "オオジシバリ": ["Ixeridium dentatum"],  # 別の学名
    "ユズ": ["Citrus x junos", "Citrus medica"],  # 交雑種なので属で
    "栽培ギク": ["Chrysanthemum × morifolium", "Chrysanthemum indicum"],
    "ハイネズ": ["Juniperus conferta", "shore juniper"],  # 英名
    "ヒメバラモミ": ["Picea maximowiczii", "Maximowicz spruce"],
    "ヤマシャクヤク": ["Paeonia obovata"],  # 別学名
    "カントウヨメナ": ["Aster yomena"],  # 近縁種
    "メナモミ": ["Siegesbeckia orientalis"],  # 近縁種
    "ツキヨタケ": ["Omphalotus japonicus"],  # 別学名
}

TIMEOUT = 30

def get_inaturalist_image(query):
    """iNaturalist APIから画像URLを取得"""
    api_url = f"https://api.inaturalist.org/v1/taxa/autocomplete?q={urllib.parse.quote(query)}"

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
                        return {
                            'url': medium_url,
                            'attribution': default_photo.get('attribution', ''),
                            'taxon_name': taxon.get('name', '')
                        }
    except Exception as e:
        print(f"  Error: {e}")
    return None

def is_valid_image(filepath):
    """画像ファイルが正常かどうかを検証"""
    try:
        result = subprocess.run(['file', '-b', str(filepath)], capture_output=True)
        ftype = result.stdout.decode('utf-8', errors='ignore').strip()
        return any(x in ftype for x in ['JPEG', 'PNG', 'GIF', 'image'])
    except:
        return False

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
                if is_valid_image(filepath):
                    return True, len(data)
                else:
                    filepath.unlink()
    except Exception as e:
        print(f"  Download error: {e}")
    return False, 0

def main():
    with open(FAILED_JSON, 'r', encoding='utf-8') as f:
        failed = json.load(f)

    with open(IMAGE_LIST, 'r', encoding='utf-8') as f:
        image_data = json.load(f)

    recovered = []
    still_failed = []

    for item in failed:
        name = item['name']
        scientific = item['scientific_name']
        print(f"\n{name} ({scientific})...")

        # 代替名があればそれで検索
        alt_names = ALTERNATIVE_NAMES.get(name, [])
        queries = [scientific] + alt_names

        found = False
        for query in queries:
            print(f"  試行: {query}")
            info = get_inaturalist_image(query)

            if info:
                ext = '.jpg'
                filename = f"{name}{ext}"
                filepath = IMAGES_DIR / filename

                time.sleep(random.uniform(0.5, 1.0))
                success, size = download_image(info['url'], filepath)

                if success:
                    image_data.append({
                        "name": name,
                        "scientific_name": scientific,
                        "filename": filename,
                        "url": info['url'],
                        "source": "iNaturalist",
                        "attribution": info['attribution'],
                        "size": size,
                        "note": f"代替検索: {query}" if query != scientific else ""
                    })
                    recovered.append(name)
                    found = True
                    print(f"  成功! ({size // 1024}KB)")
                    break

            time.sleep(random.uniform(1.0, 2.0))

        if not found:
            still_failed.append(item)
            print(f"  取得不可")

    # 保存
    with open(IMAGE_LIST, 'w', encoding='utf-8') as f:
        json.dump(image_data, f, ensure_ascii=False, indent=2)

    with open(FAILED_JSON, 'w', encoding='utf-8') as f:
        json.dump(still_failed, f, ensure_ascii=False, indent=2)

    print(f"\n=== 結果 ===")
    print(f"回復: {len(recovered)}件 - {recovered}")
    print(f"未取得: {len(still_failed)}件")

if __name__ == "__main__":
    main()
