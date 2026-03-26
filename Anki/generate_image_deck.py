#!/usr/bin/env python3
"""
ダウンロード済み画像から画像識別用Ankiデッキを生成
"""

import json
import re
from pathlib import Path
from collections import defaultdict

# 設定
ANKI_DIR = Path(__file__).parent
PART2_DIR = ANKI_DIR.parent / "Part2"
IMAGES_DIR = Path.home() / "Documents/private_matters/20260115plants_images"
IMAGE_LIST = ANKI_DIR / "image_list.json"
OUTPUT_DIR = Path.home() / "Documents/Basecamp/98_Anki/生物分類技能検定"
OUTPUT_FILE = OUTPUT_DIR / "Part2_画像識別.md"

# 科と植物の対応を抽出するための正規表現
PLANT_PATTERN = r'\|\s*\[([^\]]+)\]\([^)]+\)\s*\|\s*\*([^*]+)\*'

def load_plant_family_mapping():
    """Part2ファイルから植物名→科のマッピングを作成"""
    mapping = {}

    for md_file in sorted(PART2_DIR.glob("*.md")):
        content = md_file.read_text(encoding='utf-8')

        # 現在の科を追跡
        current_family = None

        # 科名を含む見出しを探す
        for line in content.split('\n'):
            # 科名の見出しを検出
            family_match = re.search(r'##.*?(\w+科)', line)
            if family_match:
                current_family = family_match.group(1)

            # 植物名を検出（テーブル形式）
            plant_match = re.search(r'\|\s*\[([^\]]+)\]', line)
            if plant_match and current_family:
                plant_name = plant_match.group(1).strip()
                if plant_name not in mapping:
                    mapping[plant_name] = current_family

            # 学名も取得
            sci_match = re.search(r'\*([A-Z][a-z]+(?:\s+[a-z]+)*)\*', line)
            if sci_match and plant_match:
                plant_name = plant_match.group(1).strip()
                if plant_name in mapping:
                    mapping[plant_name] = (mapping[plant_name], sci_match.group(1))

    return mapping

def load_image_data():
    """ダウンロード済み画像データを読み込み"""
    with open(IMAGE_LIST, 'r', encoding='utf-8') as f:
        return json.load(f)

def get_plant_info_from_part2(plant_name):
    """Part2ファイルから植物の詳細情報を取得"""
    info = {
        'family': None,
        'scientific_name': None,
        'features': [],
        'habitat': None
    }

    for md_file in sorted(PART2_DIR.glob("*.md")):
        content = md_file.read_text(encoding='utf-8')

        # 植物名を含む行を検索
        for i, line in enumerate(content.split('\n')):
            if f'[{plant_name}]' in line or f'| {plant_name} |' in line:
                # テーブル行から情報を抽出
                parts = line.split('|')
                if len(parts) >= 4:
                    # 学名
                    sci_match = re.search(r'\*([^*]+)\*', line)
                    if sci_match:
                        info['scientific_name'] = sci_match.group(1)

                    # 特徴（最後のカラム）
                    if len(parts) >= 5:
                        features = parts[-2].strip()
                        if features:
                            info['features'] = [f.strip() for f in features.split('、') if f.strip()]

                # 科名を遡って探す
                lines = content.split('\n')
                for j in range(i, -1, -1):
                    family_match = re.search(r'##.*?(\w+科)', lines[j])
                    if family_match:
                        info['family'] = family_match.group(1)
                        break

                if info['family']:
                    return info

    return info

def generate_deck():
    """画像識別用Ankiデッキを生成"""
    image_data = load_image_data()

    # 除外する非植物画像
    exclude = ['K-Pg境界', 'アコニチン', 'アマモ場', 'ひっつき虫', 'Heterotropa',
               'アルカロイド', 'アリストロキア酸']

    # 植物画像のみフィルタ
    plant_images = [img for img in image_data
                    if img['name'] not in exclude
                    and not any(kw in img['name'] for kw in ['酸', '毒', '境界'])]

    print(f"Total plant images: {len(plant_images)}")

    # Ankiデッキを生成
    deck_content = """# Part2 画像識別問題 - Ankiデッキ

TARGET DECK: 生物分類技能検定::Part2::画像識別

---

## 使い方

このデッキは植物の写真から種名を答える識別問題です。
画像はWikimedia Commonsから取得しています。

---

"""

    for img in sorted(plant_images, key=lambda x: x['name']):
        name = img['name']
        filename = img['filename']
        note = img.get('note', '')  # 属または近縁種の画像などの注記

        # Part2から植物情報を取得
        info = get_plant_info_from_part2(name)

        # 回答部分を構成
        answer_parts = [f"**{name}**"]

        if info['scientific_name']:
            answer_parts.append(f"学名: *{info['scientific_name']}*")

        if info['family']:
            answer_parts.append(f"科: {info['family']}")

        if info['features']:
            answer_parts.append(f"特徴: {', '.join(info['features'][:3])}")

        # 注記がある場合は追加（属や近縁種の画像の場合）
        if note:
            answer_parts.append(f"⚠️ {note}")

        answer = "<br>".join(answer_parts)

        # カードを生成（vault内の相対パスで画像参照）
        # images/ はシンボリックリンクで実際の画像フォルダを指す
        deck_content += f"""START
Basic
この植物の名前は？
![](images/{filename})
Back: {answer}
Tags: 画像識別 {info['family'] if info['family'] else ''}
END

"""

    # ファイルに書き出し
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(deck_content)

    print(f"Generated: {OUTPUT_FILE}")
    print(f"Total cards: {len(plant_images)}")

if __name__ == "__main__":
    generate_deck()
