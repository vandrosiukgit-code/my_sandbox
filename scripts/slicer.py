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
    # Убедимся, что папка для сохранения существует
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
        print(f"Создана директория: {output_folder}")

    img = Image.open(image_path).convert("RGBA")

    ranks = ["a", "2", "3", "4", "5", "6", "7", "8", "9", "10", "j", "q", "k"]
    suits = ["hearts", "diamonds", "clubs", "spades"]

    if preview_only:
        # Создаем слой для отрисовки сетки поверх изображения
        overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(overlay)
        # Пытаемся загрузить шрифт покрупнее, если не выйдет — используем стандартный
        try:
            font = ImageFont.truetype("arial.ttf", 20)
        except:
            font = ImageFont.load_default()

    for r in range(rows):
        for c in range(cols):
            # Расчет координат
            x = start_x + c * (card_w + gap_x)
            y = start_y + r * (card_h + gap_y)

            filename = f"{ranks[c]}_of_{suits[r]}.png"
            file_path = os.path.join(output_folder, filename)

            if preview_only:
                # Рисуем рамку и подпись
                draw.rectangle([x, y, x + card_w, y + card_h], outline="red", width=3)
                draw.text((x + 5, y + 5), filename, fill="red", font=font)
            else:
                # Обрезаем и сохраняем
                card_img = img.crop((x, y, x + card_w, y + card_h))
                card_img.save(file_path)

    if preview_only:
        preview_output = os.path.join(os.path.dirname(image_path), "preview_layout.png")
        result = Image.alpha_composite(img, overlay)
        result.save(preview_output)
        print(f"--- РЕЖИМ ПРЕДПРОСМОТРА ---")
        print(f"Файл превью сохранен: {preview_output}")
        print("Проверьте границы. Если всё хорошо, установите preview_only=False")
    else:
        print(f"--- ГОТОВО ---")
        print(f"Все 52 карты сохранены в: {output_folder}")


# --- НАСТРОЙКИ ---
params = {
    "image_path": r"C:\Users\Zver\Documents\Codex\2026-04-26\Sandbox\assets\main_screen\gaming_cards_set.png",
    "output_folder": r"C:\Users\Zver\Documents\Codex\2026-04-26\Sandbox\assets\main_screen\cards",
    "start_x": 11,  # Подкорректируйте после проверки превью
    "start_y": 10,  # Подкорректируйте после проверки превью
    "card_w": 126,
    "card_h": 189,
    "gap_x": 10.2,
    "gap_y": 10,
    "rows": 4,
    "cols": 13,
    "preview_only": False  # <--- Сначала True, после проверки ставьте False
}

if __name__ == "__main__":
    process_cards(**params)