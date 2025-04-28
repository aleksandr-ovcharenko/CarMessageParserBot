import asyncio
import json
import logging
import re
from collections import defaultdict

from pyrogram import Client, filters
from pyrogram.types import Message

from config import ALLOWED_USERS, API_TOKEN, API_ID, API_HASH, BOT_TOKEN
from parser import parse_car_text, load_brand_list
from utils import send_to_api
from api_ninjas import get_car_info_from_ninjas

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s'
)

# Suppress Pyrogram's internal logging
pyrogram_logger = logging.getLogger("pyrogram")
pyrogram_logger.setLevel(logging.WARNING)  # Set to WARNING to hide INFO messages

user_sessions = defaultdict(dict)

app = Client("car_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)


@app.on_message(filters.private & filters.user(ALLOWED_USERS))
async def handle_message(client: Client, message: Message):
    user_id = message.from_user.id
    print(f"[LOG] Message from {user_id}: {message.text or 'photo'}")

    session = user_sessions[user_id]
    session.setdefault("images", [])

    # --- Обработка альбома (media group)
    if message.media_group_id:
        session.setdefault("group_id", message.media_group_id)

        fid = message.photo.file_id
        if fid not in session["images"]:
            session["images"].append(fid)

        if message.caption:
            session["caption"] = message.caption
            await asyncio.sleep(2)  # подождём, пока придут все фото

            logging.info(f"[SESSION] Собрано {len(session['images'])} фото, caption получен. Отправка...")
            await process_session(message, session)
        return

    # --- Одиночное фото
    if message.photo:
        fid = message.photo.file_id
        if fid not in session["images"]:
            session["images"].append(fid)
        await message.reply("📷 Фото получено. Жду текстовое описание.")
        return

    # --- Только текст
    if message.text:
        session["caption"] = message.text
        await process_session(message, session)
        return


async def process_session(message: Message, session: dict):
    user_id = message.from_user.id
    images = session.get("images", [])
    caption = session.get("caption", "")

    try:
        if not images:
            await message.reply("⚠️ Нет фотографий. Сначала пришлите фото, потом описание.")
            return

        # Only use parse_car_text, which handles Ninja fallback internally
        car_data, failed_keys = parse_car_text(caption, return_failures=True)

        # Extract the brand, model, and modification from car_data
        brand = car_data.get("brand", "")
        model = car_data.get("model", "")
        modification = car_data.get("modification", "")

        # Construct car_data string in the required format
        car_data_str = f"{brand} {model} {modification}".strip()
        car_data["car_data"] = car_data_str

        # Log the extracted car_data string
        print(f"[DEBUG] Extracted car_data string: {car_data_str}")
        print(f"[DEBUG] Actual fields: brand='{brand}', model='{model}', modification='{modification}'")
        print(f"[DEBUG] Engine: '{car_data.get('engine', '')}'")

        print("[REQUEST DATA]", json.dumps(car_data, ensure_ascii=False, indent=2))

        # Add image file_ids to car_data
        car_data["image_file_ids"] = images

        # Create a list to store image URLs
        image_urls = []

        print("[IMAGES SENT]")
        for idx, fid in enumerate(images, 1):
            try:
                # Construct the URL directly using the BOT_TOKEN and file_id
                # This avoids the need to call get_file which seems to be failing
                url = f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={fid}"

                # Let's just log the file_id and avoid connecting to Telegram's API in this step
                print(f"[PHOTO {idx}] file_id: {fid}")

                # Add the file_id as URL since that's what most APIs accept
                image_urls.append(fid)

            except Exception as e:
                print(f"[ERROR] Failed to process photo {idx}: {str(e)}")

        # Add the original file IDs as the image data
        # The API should handle downloading these from Telegram
        car_data["image_urls"] = image_urls
        print(f"[DEBUG] Added {len(image_urls)} image IDs to be processed by API")

        # Log the final payload before sending to API
        print("[FINAL PAYLOAD]", json.dumps({k: v for k, v in car_data.items() 
                                          if k not in ['image_file_ids', 'image_urls']}, 
                                         ensure_ascii=False, indent=2))

        logging.info(f"[DEBUG] Using API token: {API_TOKEN}")

        response = send_to_api(car_data)

        if response.ok:
            try:
                data = response.json()
            except Exception:
                data = {}

            parsed_fields = [k for k in car_data if k != "image_file_ids"]
            failed_fields = failed_keys if failed_keys else []

            msg = f"✅ Автомобиль успешно импортирован!\n"
            msg += f"🆔 ID: `{data.get('car_id', '—')}`\n"

            # Format the car brand, model and year properly
            brand = data.get('brand', '')
            model = data.get('model', '')
            year = data.get('year')

            # Only include year in parentheses if it's a valid non-zero value
            year_display = f" ({year})" if year and year != 0 and year != "0" and year != "" else ""
            msg += f"🚘 {brand} {model}{year_display}\n"

            msg += f"💰 Цена: {data.get('price', '—')}\n"

            if data.get("main_image"):
                msg += f"🖼 Главное изображение готово ✅\n"

            msg += f"📸 Галерея: {data.get('gallery_images_count', 0)} фото\n"

            if car_url := data.get("car_url"):
                msg += f"\n🔗 Ссылка на сайт:\n{car_url}\n"
            if admin_url := data.get("admin_edit_url"):
                msg += f"\n🛠 Редактировать в админке:\n{admin_url}\n"

            if parsed_fields:
                msg += "\n\n✔️ Распознаны поля:\n"
                for field in parsed_fields:
                    msg += f"• `{field}`\n"

            if failed_fields:
                msg += "\n⚠️ Не удалось распознать:\n"
                for field in failed_fields:
                    msg += f"• `{field}`\n"

            await message.reply(msg)

        else:
            logging.error("❌ Ошибка при отправке данных на API")
            logging.info(f"[STATUS] {response.status_code}")
            logging.info(f"[BODY] {response.text}")

            if response.status_code >= 500:
                await message.reply("❌ Сервер временно недоступен. Попробуйте позже.")
            else:
                await message.reply("❌ Не удалось отправить данные. Проверьте формат или попробуйте снова.")

    finally:
        user_sessions.pop(user_id, None)


app.run()
