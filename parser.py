import re


def clean_number(val):
    cleaned = re.sub(r"[^\d]", "", val)
    if not cleaned:
        print(f"[WARN] clean_number: пустое значение после очистки: {val}")
        return 0
    return int(cleaned)


def parse_car_text(text: str, return_failures=False):
    """
    Парсинг текста с описанием автомобиля.
    """
    brand_list = load_brand_list()
    data, failed = _try_structured_parse(text, brand_list)
    if not data or data.get("brand") is None:
        data, failed = _try_emoji_format_parse(text, brand_list)
        if not data or data.get("brand") is None:
            data, failed = _try_lynk_format_parse(text, brand_list)
            if not data or data.get("brand") is None:
                # Попробуем парсить без структуры
                data, failed = _try_unstructured_specs_parse(text, brand_list)
                if not data or data.get("brand") is None:
                    # Крайний случай - попробуем полностью свободный формат
                    data = parse_car_text_freeform(text, brand_list)
                    failed = []  # мы не валим на ошибке в этом режиме

    if return_failures:
        return data, failed
    return data


def detect_brand_and_model(raw_string: str, brand_list: list[str]) -> tuple[str, str]:
    """Ищет бренд в начале строки и делит её на brand и model"""
    raw = raw_string.strip().lower()

    for brand in sorted(brand_list, key=lambda x: -len(x)):  # самые длинные сначала
        if raw.startswith(brand):
            model = raw[len(brand):].strip()
            return brand.capitalize(), model

    return raw_string, ""  # fallback


def load_brand_list(filepath="brands.txt") -> list[str]:
    with open(filepath, encoding="utf-8") as f:
        return [line.strip().lower() for line in f if line.strip()]


def parse_car_text_freeform(text: str, brand_list: list[str]) -> dict:
    lines = text.splitlines()
    result = {}

    # 🧠 1-я строка — бренд + модель
    if lines:
        brand, model = detect_brand_and_model(lines[0], brand_list)
        result["brand"] = brand
        result["model"] = model

    # 📅 Поиск года
    for line in lines:
        match = re.search(r"\b(20\d{2})(?:[\/\-\.](0?[1-9]|1[0-2]))?\b", line)
        if match:
            year_str = match.group(1)  # Берём только год
            result["year"] = int(year_str)
            break

    # 🛣️ Пробег
    for line in lines:
        if "пробег" in line.lower():
            km = re.search(r"([\d\s.,]+)\s*км", line.lower())
            if km:
                result["mileage"] = clean_number(km.group(1))
            break

    # 💰 Цена
    for line in lines:
        if "цена" in line.lower() or "$" in line or "₽" in line or "¥" in line:
            price_match = re.search(r"([\d\s.,]+)", line)
            if price_match:
                result["price"] = clean_number(price_match.group(1))
                result["currency"] = detect_currency(line)
            break

    # 📜 Описание — всё остальное
    description_lines = []
    for line in lines[1:]:
        if "пробег" in line.lower() or "цена" in line.lower():
            continue
        description_lines.append(line.strip())

    result["description"] = " ".join(description_lines)

    return result


def _try_structured_parse(text: str, brand_list: list[str]) -> tuple[dict, list[str]]:
    brand_model_pattern = r"(?:Бренд|Марка):\s*(.+)"
    engine_pattern = r"Двигатель:\s*(.+)"
    patterns = {
        "price": r"Цена.*?:\s*([\d\s.,$]+)",
        "mileage": r"Пробег:\s*([\d\s.,]+)",
        "car_type": r"Тип:\s*(.+)",
        "description": r"(?:Описание|Дополнительно|Прочее):\s*(.+)"
    }

    result = {}
    failed = []

    # 🧠 Brand + Model
    match = re.search(brand_model_pattern, text, re.IGNORECASE)
    if match:
        full = match.group(1).strip()
        brand, model = detect_brand_and_model(full, brand_list)
        result["brand"] = brand
        result["model"] = model
    else:
        failed.append("brand/model")

    # ⚙️ Двигатель
    match = re.search(engine_pattern, text, re.IGNORECASE)
    if match:
        raw_engine = match.group(1).strip()
        val, extra = split_engine_and_description(raw_engine)
        result["engine"] = val

        # Переносим "хвост" в description
        if extra:
            if "description" in result:
                result["description"] += " " + extra
            else:
                result["description"] = extra
    else:
        failed.append("engine")

    # 📦 Остальные поля
    for key, pattern in patterns.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            val = match.group(1).strip()
            if key in ["price", "mileage"]:
                try:
                    val = clean_number(val)
                except:
                    pass
            result[key] = val
            # --- Add currency detection for price field ---
            if key == "price":
                # Find the line containing the price to detect currency
                price_line = None
                for line in text.splitlines():
                    if match.group(1) in line:
                        price_line = line
                        break
                if price_line:
                    result["currency"] = detect_currency(price_line)
        else:
            failed.append(key)

    return result, failed



def detect_currency(line: str) -> str:
    line = line.lower()
    if "$" in line or "usd" in line:
        return "USD"
    elif "₽" in line or "руб" in line:
        return "RUB"
    elif "¥" in line or "йен" in line or "jpy" in line:
        return "JPY"
    return "unknown"

def split_engine_and_description(engine_str: str) -> tuple[str, str]:
    """
    Делит строку двигателя на основную часть и хвост после "л.с." или "kWh"
    """
    pattern = r"(.*?(?:л\.с\.|kWh))\s*[,;:\-–]?\s*(.*)"
    match = re.match(pattern, engine_str, re.IGNORECASE)
    if match:
        main = match.group(1).strip()
        extra = match.group(2).strip()
        return main, extra
    return engine_str.strip(), ""


def _try_emoji_format_parse(text: str, brand_list: list[str]) -> tuple[dict, list[str]]:
    """
    Парсер для сообщений с эмодзи и символами формата:
    🔹Geely Coolray 260T Battle
    🔹Год: 10/2020
    🔹Пробег: 35.000km
    ⚙️ДВС: 1.5Т 177 л.с.
    🔩Трансмиссия: DCT7
    🛞Привод: Передний
    💸Цена под ключ в РФ: 1.414.000 руб.
    """
    result = {}
    failed = []
    
    # Разделяем на строки и убираем пустые
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    
    # Ищем строки с названием модели (обычно в начале)
    brand_model_line = None
    
    # Специальная проверка для Mercedes и других строк в формате "BRAND MODEL CLASS YEAR"
    for i, line in enumerate(lines[:5]):  # Проверяем первые 5 строк
        # Особая проверка для Mercedes формата
        if "MERCEDES" in line or "BENZ" in line:
            brand_model_line = line
            break
            
        # Проверка для линий с эмодзи автомобиля
        if "🚗" in line or "🚙" in line or "🚘" in line:
            brand_model_line = line
            break
        
        # Общая проверка на любой бренд из списка
        for brand in brand_list:
            if brand.lower() in line.lower():
                brand_model_line = line
                break
                
        if brand_model_line:
            break
    
    # Если нашли строку с брендом и моделью
    if brand_model_line:
        # Очищаем строку от эмодзи и других символов
        clean_brand_model = re.sub(r'[^\w\s]', ' ', brand_model_line)
        # Удаляем китайские иероглифы и другие не-ASCII символы
        clean_brand_model = re.sub(r'[^\x00-\x7F]+', ' ', clean_brand_model)
        clean_brand_model = re.sub(r'\s+', ' ', clean_brand_model).strip()
        
        # Пробуем найти Mercedes-специфичный формат (MERCEDES BENZ C CLASS 2016)
        if "MERCEDES" in clean_brand_model or "BENZ" in clean_brand_model:
            # Выделяем год, если он есть
            year_in_name = re.search(r'(20\d{2})', clean_brand_model)
            if year_in_name:
                result["year"] = int(year_in_name.group(1))
                # Убираем год из строки
                clean_brand_model = re.sub(r'20\d{2}', '', clean_brand_model).strip()
            
            parts = clean_brand_model.split()
            if len(parts) >= 2:
                # Для Mercedes обычно формат: MERCEDES BENZ C CLASS
                result["brand"] = "Mercedes-Benz"
                
                # Определяем модель: все после "BENZ" или "MERCEDES"
                if "BENZ" in parts:
                    benz_index = parts.index("BENZ")
                    result["model"] = " ".join(parts[benz_index + 1:]).lower()
                else:
                    merc_index = parts.index("MERCEDES")
                    if merc_index + 1 < len(parts):
                        result["model"] = " ".join(parts[merc_index + 1:]).lower()
                    else:
                        result["model"] = ""
            else:
                result["brand"] = "Mercedes-Benz"
                result["model"] = ""
        # Особая обработка для BYD моделей
        elif "BYD" in clean_brand_model:
            result["brand"] = "BYD"
            # Ищем модель после "BYD"
            parts = clean_brand_model.split()
            if len(parts) > 1 and parts[0].upper() == "BYD":
                # Берем только английские названия (Song, Pro и т.д.)
                model_parts = []
                for part in parts[1:]:
                    if re.match(r'^[a-zA-Z0-9]+$', part):  # Только ASCII буквы и цифры
                        model_parts.append(part)
                result["model"] = " ".join(model_parts).lower()
            else:
                result["model"] = ""
        else:
            # Стандартная обработка для других брендов
            brand, model = detect_brand_and_model(clean_brand_model, brand_list)
            result["brand"] = brand
            result["model"] = model
    else:
        failed.append("brand/model")
    
    # Год выпуска (Год: XX/XXXX или просто XXXX)
    if "year" not in result:  # Проверяем, не был ли год найден ранее
        year_pattern = r"[Гг]од:?\s*(?:\d+[\/\.])?(\d{4})"
        for line in lines:
            match = re.search(year_pattern, line)
            if match:
                year_str = match.group(1)
                result["year"] = int(year_str)
                break
    
    # Пробег (Пробег: XX.XXXkm или просто цифры + km/км)
    mileage_pattern = r"[Пп]робег:?\s*([\d\s\.,]+)(?:km|км|тыс\.км|тыс|т\.км|Km)"
    for line in lines:
        match = re.search(mileage_pattern, line)
        if match:
            mileage_str = match.group(1)
            result["mileage"] = clean_number(mileage_str)
            break
    
    # Если пробег не найден, ищем дополнительно в тексте
    if "mileage" not in result:
        # Ищем формат "X.XXXKm!!!" или подобные
        extra_mileage_pattern = r"(\d[\d\s\.,]*)\s*(?:Km|km|км)"
        for line in lines:
            match = re.search(extra_mileage_pattern, line)
            if match:
                mileage_str = match.group(1)
                result["mileage"] = clean_number(mileage_str)
                break
    
    # Двигатель: ДВС/Двигатель: X.XТ XXX л.с.
    engine_pattern = r"(?:ДВС|[Дд]вигатель):?\s*(.+)"
    for line in lines:
        match = re.search(engine_pattern, line)
        if match:
            raw_engine = match.group(1).strip()
            val, extra = split_engine_and_description(raw_engine)
            result["engine"] = val
            # Добавляем остаток в описание
            if extra and "description" not in result:
                result["description"] = extra
            break
    
    # Трансмиссия: АКПП/МКПП/DSG/CVT/DCT и т.д.
    transmission_pattern = r"(?:Трансмиссия|КПП):?\s*(.+)"
    for line in lines:
        match = re.search(transmission_pattern, line)
        if match:
            result["transmission"] = match.group(1).strip()
            break
    
    # Привод: Полный/Передний/Задний/4WD/AWD и т.д.
    drive_pattern = r"(?:Привод):?\s*(.+)"
    for line in lines:
        match = re.search(drive_pattern, line)
        if match:
            result["drive_type"] = match.group(1).strip()
            break
    
    # Цена: различные форматы с валютой
    price_patterns = [
        r"(?:Цена|Стоимость|💸|[Ии]тогов)[^\d]*?([\d\s\.,]+)[^\d]*(руб|₽|\$|USD|EUR|€)",
        r"([\d\s\.,]+)(?:\s*)(?:руб|₽|\$|USD|EUR|€)",
    ]
    
    for pattern in price_patterns:
        for line in lines:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                price_str = match.group(1)
                try:
                    result["price"] = clean_number(price_str)
                    result["currency"] = detect_currency(line)
                except:
                    # Защита от ошибок при парсинге цены
                    pass
                break
        if "price" in result:
            break
    
    # Все неопознанные строки объединяем в описание
    if "description" not in result:
        # Фильтруем строки, которые уже были обработаны
        desc_lines = []
        for line in lines[1:]:
            # Пропускаем строки, содержащие уже обработанные паттерны
            if (
                ("year" in result and re.search(r"20\d{2}", line)) 
                or ("mileage" in result and re.search(mileage_pattern, line))
                or ("engine" in result and re.search(engine_pattern, line))
                or ("transmission" in result and re.search(transmission_pattern, line))
                or ("drive_type" in result and re.search(drive_pattern, line))
                or ("price" in result and any(re.search(p, line) for p in price_patterns))
            ):
                continue
                
            # Пропускаем строки, которые похожи на заголовок с брендом/моделью
            if line == brand_model_line:
                continue
                
            cleaned_line = re.sub(r'[^\w\s]', ' ', line)  # Убираем эмодзи и символы
            cleaned_line = re.sub(r'\s+', ' ', cleaned_line).strip()  # Нормализуем пробелы
            
            if cleaned_line:
                desc_lines.append(cleaned_line)
        
        if desc_lines:
            result["description"] = " ".join(desc_lines)
    
    # Определяем список не найденных полей
    if "brand" not in result:
        failed.append("brand")
    if "model" not in result:
        failed.append("model")
    if "year" not in result:
        failed.append("year")
    if "price" not in result:
        failed.append("price")
    if "mileage" not in result:
        failed.append("mileage")
    
    return result, failed


def _try_lynk_format_parse(text: str, brand_list: list[str]) -> tuple[dict, list[str]]:
    """
    Парсер для сообщений в формате Lynk & Co:
    Lynk&Co 09 MHEV 7 мест 
    
    В НАЛИЧИИ в Москве новый автомобиль
    Стоимость 5.100.000 с коммерческим утильсбором
    
    Платформа SPA (на ней же VOLVO XC90)
    Двигатель VEA (VOLVO ENGINE ARCHITECTURE)
    Двигатель 2.0Т - 254 лс 
    АКПП - 8ст автомат - AISIN
    Полный привод - Haldex 
    ...
    """
    result = {}
    failed = []
    
    # Разделяем на строки и убираем пустые
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return {}, ["empty_text"]
    
    # Проверка на первую строку с Lynk&Co
    first_line = lines[0]
    
    # Более строгий поиск с явным указанием Lynk&Co
    lynk_match = re.search(r'Lynk\s*&?\s*Co', first_line, re.IGNORECASE)
    if lynk_match:
        # Выделяем бренд и модель
        result["brand"] = "Lynk & Co"
        
        # Ищем модель (обычно число после Lynk&Co)
        model_match = re.search(r'Lynk\s*&?\s*Co\s+(\d+)', first_line, re.IGNORECASE)
        if model_match:
            result["model"] = model_match.group(1)
            
            # Ищем дополнительную информацию о модели (MHEV, PHEV и т.д.)
            model_info = re.sub(r'Lynk\s*&?\s*Co\s+\d+\s*', '', first_line, flags=re.IGNORECASE).strip()
            if model_info:
                result["model"] += " " + model_info
        else:
            result["model"] = re.sub(r'Lynk\s*&?\s*Co\s*', '', first_line, flags=re.IGNORECASE).strip()
    else:
        # Если это не формат Lynk&Co, возвращаем пустой результат
        return {}, ["not_lynk_format"]
    
    # Поиск цены
    price_patterns = [
        r"[Сс]тоимость\s*[-–]\s*([\d\s\.,]+)",
        r"[Сс]тоимость\s+([\d\s\.,]+)",
        r"[Цц]ена\s*[-–]\s*([\d\s\.,]+)",
        r"[Цц]ена\s+([\d\s\.,]+)",
        r"([\d\s\.,]+)\s*(?:руб|₽|\$|USD|EUR|€)"
    ]
    
    for pattern in price_patterns:
        for line in lines:
            match = re.search(pattern, line)
            if match:
                price_str = match.group(1)
                try:
                    # Очищаем строку цены от всего кроме цифр
                    result["price"] = clean_number(price_str)
                    # Определяем валюту
                    if "$" in line or "USD" in line or "долларов" in line:
                        result["currency"] = "USD"
                    elif "€" in line or "EUR" in line or "евро" in line:
                        result["currency"] = "EUR"
                    else:
                        result["currency"] = "RUB"  # По умолчанию рубли
                except:
                    pass
                break
        if "price" in result:
            break
    
    # Поиск года выпуска
    year_patterns = [
        r'(\b20\d{2}\b)\s*(?:г\.в\.|год|г\.|года)',  # 4-значный год начиная с 20 с указанием что это год
        r'(\b20\d{2}\b)',  # просто 4-значный год
    ]
    
    for pattern in year_patterns:
        for line in lines:
            match = re.search(pattern, line)
            if match:
                try:
                    year = int(match.group(1))
                    if 2000 <= year <= 2030:  # Разумный диапазон лет
                        result["year"] = year
                        break
                except:
                    pass
        if "year" in result:
            break
    
    # Поиск двигателя
    engine_patterns = [
        r"[Дд]вигатель.*?(\d+[\.,]?\d*\s*[ТТtT].*?(?:\d+\s*(?:л\.с\.|лс)))",
        r"[Дд]вигатель.*?(\d+[\.,]?\d*\s*-\s*\d+\s*(?:л\.с\.|лс))",
        r"[Дд]вигатель\s+(.*?\d+\s*(?:л\.с\.|лс))",
        r"[Дд]вигатель\s+([^\n\r\(]+)(?:\(|$)",
        r"[Дд]вигатель\s+([^-\n\r\(]+)(?:-|$)"  # Для строк типа "Двигатель VEA"
    ]
    
    for pattern in engine_patterns:
        for line in lines:
            match = re.search(pattern, line)
            if match:
                engine_info = match.group(1).strip()
                result["engine"] = engine_info
                break
        if "engine" in result:
            break
    
    # Если двигатель не найден, ищем по другим паттернам
    if "engine" not in result:
        for line in lines:
            # Ищем строку вида "Двигатель 2.0Т - 254 лс"
            match = re.search(r'[Дд]вигатель\s+(\d+[\.,]?\d*\s*[ТТtT])\s*-\s*(\d+)\s*(?:л\.с\.|лс)', line)
            if match:
                engine_type = match.group(1).strip()
                power = match.group(2).strip()
                result["engine"] = f"{engine_type} {power} л.с."
                break
            
    # Поиск трансмиссии
    transmission_patterns = [
        r"(?:АКПП|КПП|трансмиссия)\s*[-:]\s*([^,\n\r]+)",
        r"(?:АКПП|КПП|трансмиссия)\s+([^,\n\r]+)"
    ]
    
    for pattern in transmission_patterns:
        for line in lines:
            match = re.search(pattern, line)
            if match:
                result["transmission"] = match.group(1).strip()
                break
        if "transmission" in result:
            break
    
    # Поиск привода
    drive_patterns = [
        r"[Пп]олный\s+привод\s*[-:]\s*([^,\n\r]+)",
        r"[Пп]олный\s+привод\s*-\s*([^,\n\r]+)",
        r"[Пп]олный\s+привод",
        r"[Пп]ередний\s+привод",
        r"[Зз]адний\s+привод"
    ]
    
    for pattern in drive_patterns:
        for line in lines:
            match = re.search(pattern, line)
            if match and len(match.groups()) > 0:
                drive_info = match.group(1).strip()
                if drive_info:
                    result["drive_type"] = "Полный привод - " + drive_info
                else:
                    result["drive_type"] = "Полный привод"
                break
            elif match:
                # Паттерн без групп - определяем тип привода из паттерна
                if "полный" in pattern.lower():
                    result["drive_type"] = "Полный привод"
                elif "передний" in pattern.lower():
                    result["drive_type"] = "Передний привод"
                elif "задний" in pattern.lower():
                    result["drive_type"] = "Задний привод"
                break
        if "drive_type" in result:
            break
    
    # Поиск пробега или максимальной скорости (часто указывается как лимитер)
    mileage_patterns = [
        r"(?:пробег|км|kmh|километр|пробег):?\s*[^\d]*([\d\.,\s]+)",
        r"(?:\d+[\.,]?\d*)\s*(?:km|км|тыс[\.\s]*км)"
    ]
    
    for pattern in mileage_patterns:
        for line in lines:
            match = re.search(pattern, line)
            if match:
                try:
                    mileage_str = match.group(1).strip()
                    result["mileage"] = clean_number(mileage_str)
                    break
                except:
                    pass
        if "mileage" in result:
            break
    
    # Составляем описание из всех строк, которые не были обработаны
    desc_lines = []
    
    # Добавляем строки, которые могут быть важными
    for i, line in enumerate(lines):
        # Пропускаем первую строку с брендом/моделью
        if i == 0:
            continue
            
        # Добавляем описательные строки
        if ("наличии" in line.lower() or 
            "стоимость" in line.lower() or 
            "цена" in line.lower() or
            "бак" in line.lower() or
            "расход" in line.lower() or
            "мест" in line.lower() or
            "запуск" in line.lower() or
            "круиз" in line.lower() or
            "удержани" in line.lower()):
            desc_lines.append(line)
    
    if desc_lines:
        result["description"] = " | ".join(desc_lines)
    
    return result, failed


def _try_unstructured_specs_parse(text: str, brand_list: list[str]) -> tuple[dict, list[str]]:
    """
    Парсер для сообщений со спецификациями без явного указания бренда и модели:
    
    Стоимость – 5 700 000 руб. 
    (Коммерческий утиль)

    Новый авто
    2024 г.в.
    Максимальная комплектация, рестайлинг!
    555 лс
    Полный привод
    Параллельный гибрид (двигатель напрямую подключается к колесам через редуктор)
    6 мест
    Запас хода на чистом электричестве - 160км батарея 40 кВтч
    Пневмоподвеска
    """
    result = {}
    failed = []
    
    # Разделяем на строки и убираем пустые
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return {}, ["empty_text"]
    
    # Поиск цены
    price_patterns = [
        r"[Сс]тоимость\s*[-–]\s*([\d\s\.,]+)\s*(?:руб|₽)",
        r"[Сс]тоимость\s+([\d\s\.,]+)\s*(?:руб|₽)",
        r"[Цц]ена\s*[-–]\s*([\d\s\.,]+)\s*(?:руб|₽)",
        r"[Цц]ена\s+([\d\s\.,]+)\s*(?:руб|₽)",
        r"([\d\s\.,]+)\s*(?:руб|₽)"
    ]
    
    for pattern in price_patterns:
        for line in lines:
            match = re.search(pattern, line)
            if match:
                price_str = match.group(1)
                try:
                    result["price"] = clean_number(price_str)
                    # Определяем валюту исходя из текста
                    if "$" in line or "USD" in line or "долларов" in line:
                        result["currency"] = "USD"
                    elif "€" in line or "EUR" in line or "евро" in line:
                        result["currency"] = "EUR"
                    else:
                        result["currency"] = "RUB"  # По умолчанию рубли
                except:
                    pass
                break
        if "price" in result:
            break
    
    # Поиск года выпуска
    year_patterns = [
        r'(\b20\d{2}\b)\s*(?:г\.в\.|год|г\.|года)',  # 4-значный год начиная с 20 с указанием что это год
        r'(\b20\d{2}\b)',  # просто 4-значный год
    ]
    
    for pattern in year_patterns:
        for line in lines:
            match = re.search(pattern, line)
            if match:
                try:
                    year = int(match.group(1))
                    if 2000 <= year <= 2030:  # Разумный диапазон лет
                        result["year"] = year
                        break
                except:
                    pass
        if "year" in result:
            break
    
    # Поиск мощности двигателя и создание структуры engine
    power_patterns = [
        r'(\d+)\s*(?:л\.с\.|лс|л/с|hp)', # число + л.с./лс/hp
    ]
    
    for pattern in power_patterns:
        for line in lines:
            match = re.search(pattern, line)
            if match:
                try:
                    power = match.group(1).strip()
                    # Проверяем, была ли найдена информация о двигателе
                    if "engine" in result:
                        # Дополняем информацию о мощности
                        result["engine"] += f", {power} л.с."
                    else:
                        # Создаем новую запись
                        result["engine"] = f"{power} л.с."
                    break
                except:
                    pass
        if "engine" in result:
            break
    
    # Поиск типа двигателя
    engine_type_patterns = [
        r'[Пп]араллельный\s+гибрид',
        r'[Гг]ибрид',
        r'[Бб]ензин',
        r'[Дд]изель',
        r'[Ээ]лектро',
        r'[Тт]урбо'
    ]
    
    for pattern in engine_type_patterns:
        for line in lines:
            match = re.search(pattern, line)
            if match:
                engine_type = match.group(0).strip()
                if "engine" in result:
                    # Если уже есть информация о мощности, добавляем тип двигателя
                    result["engine"] = f"{engine_type}, " + result["engine"]
                else:
                    # Иначе просто записываем тип двигателя
                    result["engine"] = engine_type
                break
        if "engine" in result and "гибрид" in result["engine"].lower():
            break
    
    # Поиск привода
    drive_patterns = [
        r'[Пп]олный\s+привод',
        r'[Пп]ередний\s+привод',
        r'[Зз]адний\s+привод',
        r'4WD',
        r'AWD',
        r'FWD',
        r'RWD'
    ]
    
    for pattern in drive_patterns:
        for line in lines:
            match = re.search(pattern, line)
            if match:
                drive_type = match.group(0).strip()
                if drive_type.upper() == "4WD" or drive_type.upper() == "AWD":
                    result["drive_type"] = "Полный привод"
                elif drive_type.upper() == "FWD":
                    result["drive_type"] = "Передний привод"
                elif drive_type.upper() == "RWD":
                    result["drive_type"] = "Задний привод"
                else:
                    result["drive_type"] = drive_type
                break
        if "drive_type" in result:
            break
    
    # Поиск информации о пробеге или электрическом запасе хода
    ev_range = None
    mileage_patterns = [
        r'[Зз]апас\s+хода\s+.*?(\d+)\s*км',  # Запас хода ... XXX км
        r'[Пп]робег\s*[:]*\s*(\d[\d\s\.,]+)',  # Пробег: XXX
        r'(\d+[\d\s\.,]+)\s*(?:км|тыс\.км|тыс\s*км)'  # XXX км / тыс.км
    ]
    
    for pattern in mileage_patterns:
        for line in lines:
            match = re.search(pattern, line)
            if match:
                try:
                    mileage_str = match.group(1).strip()
                    parsed_mileage = clean_number(mileage_str)
                    
                    # Если это запас хода электромобиля, добавляем в описание
                    if "запас хода" in line.lower() and not ev_range:
                        ev_range = f"Запас хода: {parsed_mileage} км"
                    # Иначе это пробег автомобиля
                    elif "пробег" in line.lower() or not "запас" in line.lower():
                        result["mileage"] = parsed_mileage
                    break
                except:
                    pass
        if "mileage" in result:
            break
    
    # Составляем описание из всех строк, которые могут содержать важную информацию
    desc_lines = []
    processed_patterns = [
        r"[Сс]тоимость", r"[Цц]ена", r"\d{4}\s*г\.в\.", 
        r"\d+\s*(?:л\.с\.|лс)", r"привод"
    ]
    
    # Добавляем строки, которые не попали в основные поля
    for line in lines:
        should_add = True
        for pattern in processed_patterns:
            if re.search(pattern, line, re.IGNORECASE):
                should_add = False
                break
                
        # Добавляем строки с важной информацией в описание
        if should_add and any(keyword in line.lower() for keyword in 
                             ["комплектация", "места", "сидений", "кондиционер", 
                              "кожа", "климат", "подвеска", "пневмо", "батарея"]):
            desc_lines.append(line)
    
    if desc_lines:
        description = " | ".join(desc_lines)
        if "description" in result:
            result["description"] += " | " + description
        else:
            result["description"] = description
    
    # Добавляем запас хода в описание, если он был найден
    if ev_range:
        if "description" in result:
            result["description"] = ev_range + " | " + result["description"]
        else:
            result["description"] = ev_range
    
    # Если брэнд и модель отсутствуют, используем заглушку
    if "brand" not in result:
        result["brand"] = "Неизвестно"
    if "model" not in result:
        result["model"] = "Неизвестно"
    
    return result, failed