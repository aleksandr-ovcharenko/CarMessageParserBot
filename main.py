import asyncio
import json
import logging
from collections import defaultdict

from pyrogram import Client, filters
from pyrogram.types import Message

from config import ALLOWED_USERS, API_TOKEN, API_ID, API_HASH, BOT_TOKEN
from parser import parse_car_text
from utils import send_to_api

logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s'
)

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

        car_data, failed_keys = parse_car_text(caption, return_failures=True)
        if not car_data:
            await message.reply("❌ Не удалось распарсить сообщение. Убедитесь в правильности формата.")
            return

        print("[REQUEST DATA]", json.dumps(car_data, ensure_ascii=False, indent=2))

        car_data["image_file_ids"] = images

        print("[IMAGES SENT]")
        for idx, fid in enumerate(images, 1):
            try:
                file = await message._client.get_file(fid)
                url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file.file_path}"
            except Exception:
                url = "—"

            print(f"[PHOTO {idx}] file_id: {fid}")
            print(f"           URL: {url}")

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
            msg += f"🚘 {data.get('brand', '')} {data.get('model', '')} ({data.get('year', '')})\n"
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
