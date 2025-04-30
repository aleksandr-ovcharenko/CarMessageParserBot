import asyncio
import json
import logging
from collections import defaultdict

from pyrogram import Client, filters
from pyrogram.types import Message

from config import ALLOWED_USERS, API_TOKEN, API_ID, API_HASH, BOT_TOKEN
from parser import parse_car_text
from utils import send_to_api

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

        # Add chat_id to payload for server-side async handling
        car_data["chat_id"] = message.chat.id

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

        # Add image URLs to car_data
        # The API should handle downloading these from Telegram
        car_data["image_urls"] = image_urls
        print(f"[DEBUG] Added {len(image_urls)} image IDs to be processed by API")

        # Log the final payload before sending to API
        print("[FINAL PAYLOAD]", json.dumps({k: v for k, v in car_data.items()
                                             if k not in ['image_file_ids', 'image_urls']},
                                            ensure_ascii=False, indent=2))

        logging.info(f"[DEBUG] Using API token: {API_TOKEN}")

        # Send immediate confirmation to user with the parsed data
        human_readable = format_car_data_for_human(car_data)
        await message.reply(
            f"✅ Получены данные о автомобиле. Отправляю запрос на сервер...\n\n"
            f"{human_readable}\n\n"
            f"Пожалуйста, подождите. Я сообщу о результате обработки."
        )

        # Start async task to send data to API and handle response
        asyncio.create_task(send_api_request_and_notify(message, car_data))
        
        # Clear the images and caption from the session after processing
        session["images"] = []
        session.pop("caption", None)
        session.pop("group_id", None)

    except Exception as e:
        print(f"[ERROR] Failed to process: {str(e)}")
        await message.reply(f"⚠️ Ошибка при обработке: {str(e)}")


async def send_api_request_and_notify(message, car_data):
    """Sends request to API and notifies user about result"""
    try:
        # Send to API
        response = await send_to_api(car_data, API_TOKEN)
        
        # Process response - expected to be immediate acknowledgment first
        if response.status_code >= 200 and response.status_code < 300:
            try:
                data = response.json()
                
                # Handle the new "received" status format
                if data.get("status") == "received":
                    # The server has received the request and will process it asynchronously
                    # No need to send additional message since we already sent the initial confirmation
                    print(f"[API] Request received by server: {data.get('message', '')}")
                    # Server will send follow-up notification directly to the user's chat
                    return
                
                # If we get a full response (legacy or direct processing), handle it
                msg = f"✅ Автомобиль успешно импортирован!\n"
                msg += f"🆔 ID: `{data.get('car_id', '—')}`\n"

                # Format the car brand, model and year properly
                brand = data.get('brand', '')
                model = data.get('model', '')
                year = data.get('year', '')

                # Only include year in parentheses if it's a valid non-zero value
                year_display = f" ({year})" if year and year != 0 and year != "0" and year != "" else ""
                msg += f"🚘 {brand} {model}{year_display}\n"

                msg += f"💰 Цена: {data.get('price', '—')}\n"

                if data.get("main_image"):
                    msg += f"🖼 Главное изображение готово ✅\n"

                msg += f"📸 Галерея: {data.get('gallery_images_count', 0)} фото\n"
                
                # Add URLs if provided
                if car_url := data.get("car_url"):
                    msg += f"\n🔗 Ссылка на сайт:\n{car_url}\n"
                if admin_url := data.get("admin_edit_url"):
                    msg += f"\n🛠 Редактировать в админке:\n{admin_url}\n"

                await message.reply(msg)
            except Exception as e:
                print(f"[ERROR] Failed to parse API response: {str(e)}")
                await message.reply(f"⚠️ Получен неожиданный ответ от сервера. Обработка может быть в процессе.")
        else:
            error_msg = f"❌ Ошибка при отправке данных на сервер: {response.status_code}\n"
            if hasattr(response, 'text'):
                error_msg += f"Ответ: {response.text}"
            await message.reply(error_msg)

    except Exception as e:
        print(f"[ERROR] API CONNECTION ERROR: {str(e)}")
        await message.reply(
            f"❌ Ошибка при подключении к серверу: {str(e)}\n\nПожалуйста, попробуйте позже или проверьте доступность сервера.")


def format_car_data_for_human(car_data):
    """Formats car data for human-readable display"""
    lines = []

    # Brand, model and trim
    brand = car_data.get('brand', '—')
    model = car_data.get('model', '—')
    trim = car_data.get('trim', '')
    modification = car_data.get('modification', '')

    car_line = f"🚗 {brand} {model}"
    if trim:
        car_line += f" {trim}"
    lines.append(car_line)

    # Modification if present
    if modification:
        lines.append(f"📋 Модификация: {modification}")

    # Engine
    if engine := car_data.get('engine', ''):
        lines.append(f"⚙️ Двигатель: {engine}")

    # Year
    if year := car_data.get('year', ''):
        lines.append(f"📅 Год: {year}")

    # Mileage
    if mileage := car_data.get('mileage', ''):
        lines.append(f"🛣 Пробег: {mileage} км")

    # Price
    if price := car_data.get('price', ''):
        currency = car_data.get('currency', 'RUB')
        currency_symbol = {'USD': '$', 'RUB': '₽', 'EUR': '€'}.get(currency, '')
        lines.append(f"💰 Цена: {price} {currency_symbol}")

    # Drive type
    if drive := car_data.get('drive_type', ''):
        lines.append(f"🔄 Привод: {drive}")

    # Transmission
    if transmission := car_data.get('transmission', ''):
        lines.append(f"🔄 Трансмиссия: {transmission}")

    return "\n".join(lines)


app.run()
