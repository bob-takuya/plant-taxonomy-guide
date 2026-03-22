#!/usr/bin/env python3
"""壊れたJPEG画像を修復 - UTF-8エンコーディングで壊れた先頭バイトを修正"""
import subprocess
from pathlib import Path

IMAGES_DIR = Path.home() / "Documents/private_matters/20260115plants_images"

# UTF-8置換文字 (ef bf bd) → 元のバイトに復元するマッピング
# ef bf bd は 0xFFFD (Unicode replacement character) のUTF-8表現
# これは不正なバイト列がUTF-8として解釈された結果

fixed = 0
failed = 0

for f in IMAGES_DIR.glob("*.jpg"):
    result = subprocess.run(['file', '-b', str(f)], capture_output=True)
    ftype = result.stdout.decode('utf-8', errors='ignore').strip()

    if 'JPEG' not in ftype and 'image' not in ftype:
        print(f"Checking: {f.name}")

        with open(f, 'rb') as file:
            data = bytearray(file.read())

        # 先頭を確認
        if data[:3] == b'\xef\xbf\xbd':
            # UTF-8 BOM/replacement が入っている - JPEGヘッダを復元
            # JPEG: FF D8 FF E0 (JFIF) or FF D8 FF E1 (EXIF)

            # パターン: ef bf bd ef bf bd ef bf bd ef bf bd 00 10 4a 46 49 46
            # これは FF D8 FF E0 00 10 JFIF のはず

            # JFIF marker を探す
            jfif_pos = data.find(b'JFIF')
            exif_pos = data.find(b'Exif')

            if jfif_pos > 0 and jfif_pos < 50:
                # JFIFの前にあるべきヘッダを再構築
                # 標準JFIF: FF D8 FF E0 00 10 JFIF
                new_header = b'\xff\xd8\xff\xe0\x00\x10'
                # JFIFの位置から逆算
                new_data = new_header + data[jfif_pos:]

                with open(f, 'wb') as file:
                    file.write(new_data)

                # 検証
                result2 = subprocess.run(['file', '-b', str(f)], capture_output=True)
                if 'JPEG' in result2.stdout.decode():
                    print(f"  Fixed (JFIF): {f.name}")
                    fixed += 1
                else:
                    print(f"  Still broken: {f.name}")
                    failed += 1

            elif exif_pos > 0 and exif_pos < 50:
                # EXIFの前にあるべきヘッダを再構築
                # 標準EXIF: FF D8 FF E1 xx xx Exif
                # xxxx はセグメント長
                new_header = b'\xff\xd8\xff\xe1'
                # Exifの2バイト前からセグメント長を取得するのは難しいので
                # Exifの位置から逆算
                seg_start = exif_pos - 2  # セグメント長の位置
                if seg_start >= 4:
                    new_data = new_header + data[seg_start:]
                else:
                    new_data = new_header + b'\x00\x00' + data[exif_pos:]

                with open(f, 'wb') as file:
                    file.write(new_data)

                result2 = subprocess.run(['file', '-b', str(f)], capture_output=True)
                if 'JPEG' in result2.stdout.decode():
                    print(f"  Fixed (EXIF): {f.name}")
                    fixed += 1
                else:
                    print(f"  Still broken: {f.name}")
                    failed += 1
            else:
                print(f"  Cannot fix (no JFIF/EXIF found): {f.name}")
                failed += 1
        else:
            print(f"  Unknown corruption: {f.name} - {data[:10].hex()}")
            failed += 1

print(f"\nFixed: {fixed}, Failed: {failed}")
