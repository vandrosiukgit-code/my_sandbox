from PIL import Image, ImageDraw, ImageFont
import os


def process_cards(
        image_path,
        output_folder,
        start_x, start_y,
        card_w, card_h,
        gap_x, gap_y,
        rows, cols,
        preview_only=True
):
    # РЈР±РµРґРёРјСЃСЏ, С‡С‚Рѕ РїР°РїРєР° РґР»СЏ СЃРѕС…СЂР°РЅРµРЅРёСЏ СЃСѓС‰РµСЃС‚РІСѓРµС‚
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
        print(f"РЎРѕР·РґР°РЅР° РґРёСЂРµРєС‚РѕСЂРёСЏ: {output_folder}")

    img = Image.open(image_path).convert("RGBA")

    ranks = ["a", "2", "3", "4", "5", "6", "7", "8", "9", "10", "j", "q", "k"]
    suits = ["hearts", "diamonds", "clubs", "spades"]

    if preview_only:
        # РЎРѕР·РґР°РµРј СЃР»РѕР№ РґР»СЏ РѕС‚СЂРёСЃРѕРІРєРё СЃРµС‚РєРё РїРѕРІРµСЂС… РёР·РѕР±СЂР°Р¶РµРЅРёСЏ
        overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(overlay)
        # РџС‹С‚Р°РµРјСЃСЏ Р·Р°РіСЂСѓР·РёС‚СЊ С€СЂРёС„С‚ РїРѕРєСЂСѓРїРЅРµРµ, РµСЃР»Рё РЅРµ РІС‹Р№РґРµС‚ вЂ” РёСЃРїРѕР»СЊР·СѓРµРј СЃС‚Р°РЅРґР°СЂС‚РЅС‹Р№
        try:
            font = ImageFont.truetype("arial.ttf", 20)
        except:
            font = ImageFont.load_default()

    for r in range(rows):
        for c in range(cols):
            # Р Р°СЃС‡РµС‚ РєРѕРѕСЂРґРёРЅР°С‚
            x = start_x + c * (card_w + gap_x)
            y = start_y + r * (card_h + gap_y)

            filename = f"{ranks[c]}_of_{suits[r]}.png"
            file_path = os.path.join(output_folder, filename)

            if preview_only:
                # Р РёСЃСѓРµРј СЂР°РјРєСѓ Рё РїРѕРґРїРёСЃСЊ
                draw.rectangle([x, y, x + card_w, y + card_h], outline="red", width=3)
                draw.text((x + 5, y + 5), filename, fill="red", font=font)
            else:
                # РћР±СЂРµР·Р°РµРј Рё СЃРѕС…СЂР°РЅСЏРµРј
                card_img = img.crop((x, y, x + card_w, y + card_h))
                card_img.save(file_path)

    if preview_only:
        preview_output = os.path.join(os.path.dirname(image_path), "preview_layout.png")
        result = Image.alpha_composite(img, overlay)
        result.save(preview_output)
        print(f"--- Р Р•Р–РРњ РџР Р•Р”РџР РћРЎРњРћРўР Рђ ---")
        print(f"Р¤Р°Р№Р» РїСЂРµРІСЊСЋ СЃРѕС…СЂР°РЅРµРЅ: {preview_output}")
        print("РџСЂРѕРІРµСЂСЊС‚Рµ РіСЂР°РЅРёС†С‹. Р•СЃР»Рё РІСЃС‘ С…РѕСЂРѕС€Рѕ, СѓСЃС‚Р°РЅРѕРІРёС‚Рµ preview_only=False")
    else:
        print(f"--- Р“РћРўРћР’Рћ ---")
        print(f"Р’СЃРµ 52 РєР°СЂС‚С‹ СЃРѕС…СЂР°РЅРµРЅС‹ РІ: {output_folder}")


# --- РќРђРЎРўР РћР™РљР ---
params = {
    "image_path": r"C:\Users\Zver\Documents\Codex\2026-04-26\Sandbox\assets\main_screen\gaming_cards_set.png",
    "output_folder": r"C:\Users\Zver\Documents\Codex\2026-04-26\Sandbox\assets\main_screen\cards",
    "start_x": 11,  # РџРѕРґРєРѕСЂСЂРµРєС‚РёСЂСѓР№С‚Рµ РїРѕСЃР»Рµ РїСЂРѕРІРµСЂРєРё РїСЂРµРІСЊСЋ
    "start_y": 10,  # РџРѕРґРєРѕСЂСЂРµРєС‚РёСЂСѓР№С‚Рµ РїРѕСЃР»Рµ РїСЂРѕРІРµСЂРєРё РїСЂРµРІСЊСЋ
    "card_w": 126,
    "card_h": 189,
    "gap_x": 10.2,
    "gap_y": 10,
    "rows": 4,
    "cols": 13,
    "preview_only": False  # <--- РЎРЅР°С‡Р°Р»Р° True, РїРѕСЃР»Рµ РїСЂРѕРІРµСЂРєРё СЃС‚Р°РІСЊС‚Рµ False
}

if __name__ == "__main__":
    process_cards(**params)

