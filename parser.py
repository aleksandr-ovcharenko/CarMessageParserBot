import re
from collections import defaultdict


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
    if not data or data.get("brand") is None or not data.get("model"):
        data, failed = _try_emoji_format_parse(text, brand_list)
        if not data or data.get("brand") is None or not data.get("model"):
            data, failed = _try_lynk_format_parse(text, brand_list)
            if not data or data.get("brand") is None or not data.get("model"):
                # Попробуем парсить без структуры
                data, failed = _try_unstructured_specs_parse(text, brand_list)
                if not data or data.get("brand") is None or not data.get("model"):
                    # Используем улучшенный парсер бренда/модели
                    first_line = text.splitlines()[0] if text.splitlines() else text
                    brand, model, modifications = improved_brand_model_parse(first_line, brand_list)
                    if brand and model:
                        if not data:
                            data = {}
                        data["brand"] = brand
                        data["model"] = model
                        
                        # Process modifications to separate trim and other modifications
                        if modifications:
                            trim_and_mods = separate_trim_from_modifications(modifications)
                            if trim_and_mods.get("trim"):
                                data["trim"] = trim_and_mods["trim"]
                            if trim_and_mods.get("modification"):
                                data["modification"] = trim_and_mods["modification"]
                            
                        failed = []  # мы не валим на ошибке в этом режиме
    # --- API Ninjas fallback ---
    if (not data.get("brand") or not data.get("model")) and data.get("description"):
        try:
            from api_ninjas import get_car_info_from_ninjas
            ninjas_info = get_car_info_from_ninjas(data["description"])
            if ninjas_info:
                if ninjas_info.get("make"):
                    data["brand"] = ninjas_info["make"]
                if ninjas_info.get("model"):
                    data["model"] = ninjas_info["model"]
        except Exception as e:
            print(f"[API NINJAS FALLBACK ERROR] {e}")
    if return_failures:
        return data, failed
    return data


def detect_brand_and_model(raw_string: str, brand_list: list[str]) -> tuple[str, str]:
    """
    Ищет бренд в начале строки и делит её на brand и model.
    Возвращает бренд с оригинальным регистром (как в brands.txt), модель — первую часть после бренда (до пробела или скобки/скобок).
    Также поддерживает сокращённые формы (например, 'Li 8 Pro' → 'Li Auto', '8 Pro').
    Для строк типа 'Марка: BRAND MODEL (extra)' модель = MODEL (до скобки).
    Для 'Модель:' строк модель = полная строка.
    """
    # Default return values
    brand = ""
    model = ""
    
    # Handling "Марка:" format
    if "Марка:" in raw_string or "Бренд:" in raw_string:
        # Split by colon
        parts = re.split(r'[:：]', raw_string, 1)
        if len(parts) > 1:
            brand_model = parts[1].strip()
            return detect_brand_and_model(brand_model, brand_list)
    
    # Handle "Модель:" format differently
    if raw_string.strip().startswith("Модель:"):
        # For "Модель:" lines, consider everything after the colon as the model
        parts = re.split(r'[:：]', raw_string, 1)
        if len(parts) > 1:
            model = parts[1].strip()
            # Try to find a brand within the model
            for b in sorted(brand_list, key=len, reverse=True):
                if b.lower() in model.lower():
                    brand = b
                    # Remove brand from model
                    model = re.sub(r'(?i)\b' + re.escape(b) + r'\b', '', model).strip()
                    break
            return brand, model
    
    # Normal processing for other formats
    words = raw_string.split()
    if not words:
        return "", ""
    
    brand_map = load_brand_map()
    raw = raw_string.strip()
    raw_lower = raw.lower()
    first_word = raw.split()[0].lower() if raw.split() else ""
    # Try short form mapping FIRST using brand_map
    if first_word in brand_map:
        canonical_brand = brand_map[first_word]
        model_part = raw[len(first_word):].strip()
        model_core = re.split(r'\(', model_part)[0].strip() if model_part else ""
        model_core = re.sub(r'[А-Яа-яЁё]+', '', model_core).strip()
        model = model_core
        if not model and model_part:
            model = re.sub(r'[А-Яа-яЁё]+', '', model_part).strip()
        return canonical_brand, model
    # Try exact match
    for brand in sorted(brand_list, key=lambda x: -len(x)):
        brand_lower = brand.lower()
        if raw_lower.startswith(brand_lower):
            # Ensure we match only the brand, not a mapping line (e.g. 'li = Li Auto')
            if '=' in brand:
                continue
            model_part = raw[len(brand):].strip()
            model_core = re.split(r'\(', model_part)[0].strip() if model_part else ""
            model_core = re.sub(r'[А-Яа-яЁё]+', '', model_core).strip()
            model = model_core
            if not model and model_part:
                model = re.sub(r'[А-Яа-яЁё]+', '', model_part).strip()
            canonical_brand = brand_map.get(brand_lower, brand)
            return canonical_brand, model
    # Try partial match: first word of input matches first word of a brand
    for brand in sorted(brand_list, key=lambda x: -len(x)):
        brand_first_word = brand.split()[0].lower()
        if first_word and first_word == brand_first_word:
            model_part = raw[len(first_word):].strip()
            model_core = re.split(r'\(', model_part)[0].strip() if model_part else ""
            model_core = re.sub(r'[А-Яа-яЁё]+', '', model_core).strip()
            model = model_core
            if not model and model_part:
                model = re.sub(r'[А-Яа-яЁё]+', '', model_part).strip()
            canonical_brand = brand_map.get(brand_lower, brand)
            return canonical_brand, model
    return None, None  # fallback, not raw_string


def load_brand_list(filepath="brands.txt") -> list[str]:
    # Only return canonical brand names and synonyms, skip mapping lines
    result = []
    with open(filepath, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                left, right = [x.strip() for x in line.split('=', 1)]
                # Add both left (synonym) and right (canonical) for matching
                result.append(left)
                result.append(right)
            else:
                result.append(line)
    return result


def load_brand_map(filepath="brands.txt") -> dict:
    """Returns a mapping from each synonym/variant to canonical brand (first occurrence wins)."""
    brand_map = {}
    brand_list = load_brand_list(filepath)
    
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
                
            # Split by commas, and clean each part
            parts = [p.strip() for p in line.split(",")]  # Keep original case for the canonical brand
            if not parts:
                continue
                
            canonical = parts[0]  # First part is the canonical brand (proper case)
            
            # Map each variant (lowercase) to the canonical brand (proper case)
            for variant in parts:
                variant_lower = variant.lower()
                if variant_lower not in brand_map:  # First occurrence wins
                    brand_map[variant_lower] = canonical  # Store original case
    except Exception as e:
        print(f"Error loading brand map: {e}")
        # Return a mapping from each brand to itself if file can't be loaded
        brand_map = {b.lower(): b for b in brand_list}  # Preserve original case
        
    return brand_map


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
        # Look for price indicators including 💲, $ or word 'цена'
        if ("цена" in line.lower() or "$" in line or "₽" in line or "¥" in line or "💲" in line or "💵" in line):
            # Remove all non-digit/currency/space/emoji chars except separators
            cleaned_line = line.replace('\xa0', ' ').replace('\u202f', ' ')
            # Try to match price after any currency indicator or at end
            price_match = re.search(r"([\d][\d\s.,]*)", cleaned_line)
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
    model_line_pattern = r"(?:Модель):\s*(.+)"  # Added pattern for "Модель:" line
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
        
        # Special handling for "Бренд:" + "Модель:" format where Model line contains modifications
        model_match = re.search(model_line_pattern, text, re.IGNORECASE)
        if model_match:
            # If we have a "Модель:" line, use its content as modification
            modification = model_match.group(1).strip()
            if modification:
                result["modification"] = modification
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
    
    # Gather car-related information from first few lines
    car_info_lines = []
    found_specific_section = False
    
    # Check first few lines for car information
    for i, line in enumerate(lines[:5]):
        # Skip if we've already found a section marker
        if found_specific_section:
            break
            
        # Stop collecting if we hit a specific section
        if any(pattern in line.lower() for pattern in ["год:", "пробег:", "двс:", "трансмиссия:", "привод:", "цена:"]):
            found_specific_section = True
            break
            
        # Clean line from emojis and other symbols
        clean_line = re.sub(r'[^\w\s]', ' ', line)
        clean_line = re.sub(r'[^\x00-\x7F]+', ' ', clean_line)  # Remove non-ASCII
        clean_line = re.sub(r'\s+', ' ', clean_line).strip()
        
        if clean_line:
            car_info_lines.append(clean_line)
    
    # Combine all car info lines
    if car_info_lines:
        combined_car_info = " ".join(car_info_lines)
        
        # Now use improved_brand_model_parse to extract brand, model, and modifications
        brand, model, modification = improved_brand_model_parse(combined_car_info, brand_list)
        
        if brand:
            result["brand"] = brand
        else:
            failed.append("brand")
            
        if model:
            result["model"] = model
        else:
            failed.append("model")
            
        if modification:
            result["modification"] = modification
    else:
        failed.append("brand/model")
    
    # Continue with the rest of the parsing for other fields (year, mileage, engine, etc.)
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
            # Добавляем остаток в description
            if extra and "description" not in result:
                result["description"] = extra
            break
    
    # Трансмиссия: АКПП/МКПП/DSG/CVT/DCT и т.д.
    transmission_pattern = r"(?:АКПП|КПП|трансмиссия):?\s*[-:]\s*([^,\n\r]+)"
    for line in lines:
        match = re.search(transmission_pattern, line)
        if match:
            result["transmission"] = match.group(1).strip()
            break
    
    # Привод: Полный/Передний/Задний/4WD/AWD и т.д.
    drive_pattern = r"[Пп]ривод:?\s*(.+)"
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
            if car_info_lines and line == car_info_lines[0]:
                continue
                
            cleaned_line = re.sub(r'[^\w\s]', ' ', line)  # Убираем эмодзи и символы
            cleaned_line = re.sub(r'\s+', ' ', cleaned_line).strip()  # Нормализуем пробелы
            
            if cleaned_line:
                desc_lines.append(cleaned_line)
        
        if desc_lines:
            description = " | ".join(desc_lines)
            if "description" in result:
                result["description"] += " | " + description
            else:
                result["description"] = description
    
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
            
            # Extract modifications (everything after the model number)
            model_info = re.sub(r'Lynk\s*&?\s*Co\s+\d+\s*', '', first_line, flags=re.IGNORECASE).strip()
            if model_info:
                # Store the modification information separately
                result["modification"] = model_info
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
        r"(?:АКПП|КПП|трансмиссия):?\s*[-:]\s*([^,\n\r]+)",
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
        r"(?:\d+[\.,]?\d*)\s*(?:km|км)"
    ]
    
    for pattern in mileage_patterns:
        for line in lines:
            match = re.search(pattern, line)
            if match:
                try:
                    mileage_str = match.group(1)
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


def load_model_patterns(filepath="models.txt") -> dict:
    """
    Load model patterns from a configuration file.
    Returns a dictionary mapping brands to their model patterns.
    
    Format in the file:
    brand:pattern_type:pattern_regex
    """
    model_patterns = defaultdict(dict)
    
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
                
            parts = line.split(":", 2)  # Split into at most 3 parts
            if len(parts) < 2:
                continue
                
            brand = parts[0].lower()
            pattern_type = parts[1]
            
            # Handle the 'default' pattern type (a flag rather than a pattern)
            if pattern_type == "default":
                model_patterns[brand]["default"] = True
                continue
                
            # Get the pattern regex if provided
            pattern = parts[2] if len(parts) > 2 else ""
            
            # Initialize the pattern type if not already in the dict
            if pattern_type not in model_patterns[brand]:
                model_patterns[brand][pattern_type] = []
                    
            model_patterns[brand][pattern_type].append(pattern)
    except Exception as e:
        print(f"Error loading model patterns: {e}")
    
    return model_patterns


def improved_brand_model_parse(text: str, brand_list: list[str]) -> tuple[str, str, str]:
    """
    Enhanced parser that separates brand, model, and modifications.
    Returns a tuple of (brand, model, modifications)
    
    Uses local logic to better identify the components:
    - Brand is identified from the brand list
    - Model is the core model name that follows the brand
    - Modifications are additional descriptors, variants, trim levels, etc.
    """
    import re
    brand_map = load_brand_map()
    model_patterns = load_model_patterns()
    
    raw = text.strip()
    raw_lower = raw.lower()
    
    # Clean the text by removing parenthetical phrases first
    parentheses_content = []
    clean_raw = raw
    
    # Extract all content in parentheses and save for later
    parentheses_pattern = r'\([^)]+\)'
    for match in re.finditer(parentheses_pattern, raw):
        parentheses_content.append(match.group(0))
        clean_raw = clean_raw.replace(match.group(0), ' ')
    
    # Remove emoji and special characters for cleaner parsing
    clean_text = re.sub(r'[^\w\s\-\.]', ' ', clean_raw).strip()
    # Remove extra spaces
    clean_text = re.sub(r'\s+', ' ', clean_text)
    
    words = clean_text.split()
    if not words:
        return "", "", ""
        
    # Step 1: Identify the brand
    brand = None
    model_start_idx = 0
    
    # Try to match full brand names first (longer matches first)
    for b in sorted(brand_list, key=lambda x: -len(x)):
        b_lower = b.lower()
        if b_lower in raw_lower:
            # Check if it's at the beginning or preceded only by noise
            b_pos = raw_lower.find(b_lower)
            prefix = raw_lower[:b_pos].strip()
            if b_pos == 0 or not re.search(r'[a-zA-Z0-9]', prefix):
                # Use the proper case from brand_map here
                brand = b  # Use the original case from brand_list
                # Find where the model should start in the words list
                model_start_idx = len(prefix.split()) + len(b.split())
                break
    # If no brand found, try matching just the first word against brand names
    if not brand and words:
        first_word = words[0].lower()
        if first_word in brand_map:
            brand = brand_map[first_word]  # This uses proper case from brand_map
            model_start_idx = 1
    
    # If still no brand, try partial matching with first words
    if not brand and words:
        first_word = words[0].lower()
        for b in brand_list:
            b_parts = b.lower().split()
            if b_parts and first_word == b_parts[0]:
                brand = b  # Use original case from brand_list
                model_start_idx = 1
                break
    
    if not brand:
        return None, None, None
    
    # Step 2: Extract model and modifications
    # Get remaining text after brand
    remaining_words = words[model_start_idx:]
    if not remaining_words:
        return brand, "", ""
    
    # Normalize the brand name for pattern matching
    brand_lower = brand.lower()
    
    # Try to find model using patterns from the configuration file
    model = None
    model_end_idx = 0
    brand_lower = ""  # Initialize brand_lower with a default value
    
    # If brand has patterns defined and we have a valid brand
    if brand and brand.lower() in model_patterns:
        brand_lower = brand.lower()
        patterns = model_patterns[brand_lower]
        
        # Check if the brand uses default pattern
        if 'default' in patterns:
            # For default pattern, just take the first word as model
            model = remaining_words[0]
            model_end_idx = 1
        else:
            # Check for exact model names first
            if 'model' in patterns:
                for model_name in patterns['model']:
                    model_name_lower = model_name.lower()
                    if model_name_lower in ' '.join(remaining_words).lower():
                        # Find where in the words this model appears
                        for i, word in enumerate(remaining_words):
                            if model_name_lower in word.lower():
                                model = model_name
                                model_end_idx = i + 1  # Include this word
                                break
                        if model:
                            break
            
            # If no model found yet, try series/class patterns
            if not model and 'series_class' in patterns:
                for pattern in patterns['series_class']:
                    series_match = re.search(pattern, ' '.join(remaining_words), re.IGNORECASE)
                    if series_match:
                        # Find which words contain this match
                        match_position = series_match.start()
                        match_end_position = series_match.end()
                        
                        # Count characters to find the words that contain the match
                        start_idx = None
                        end_idx = None
                        char_count = 0
                        
                        for i, word in enumerate(remaining_words):
                            next_char_count = char_count + len(word) + 1  # +1 for space
                            if char_count <= match_position < next_char_count and start_idx is None:
                                start_idx = i
                            if char_count <= match_end_position < next_char_count:
                                end_idx = i + 1  # +1 to include this word
                                break
                            char_count = next_char_count
                        
                        if start_idx is not None and end_idx is not None:
                            model = ' '.join(remaining_words[start_idx:end_idx])
                            model_end_idx = end_idx
                            break
            
            # Try alphanumeric patterns
            if not model and 'alphanumeric' in patterns:
                for pattern in patterns['alphanumeric']:
                    for i, word in enumerate(remaining_words[:2]):  # Only check first 2 words
                        if re.match(pattern, word, re.IGNORECASE):
                            model = word
                            model_end_idx = i + 1  # Include this word
                            break
                    if model:
                        break
            
            # Try prefix-number patterns (e.g., "RX 350")
            if not model and 'prefix_number' in patterns and len(remaining_words) >= 2:
                for pattern in patterns['prefix_number']:
                    if re.match(pattern, remaining_words[0], re.IGNORECASE):
                        model = remaining_words[0]
                        model_end_idx = 1  # Just take the first word as model
                        break
    
    # If no model found using patterns, use default approach
    if not model:
        # Default: first word is model
        model = remaining_words[0]
        model_end_idx = 1
    
    # Extract modifications, but exclude certain patterns
    if len(remaining_words) > model_end_idx:
        # These are patterns that should NOT be included in the modification
        exclude_patterns = [
            r'(?:\d+)?\s*(?:места|мест|seat(?:er|s)?)',  # Seating info like "7 мест" or "7 seater"
            r'\d+\s*л\.?с\.?',  # Engine power like "220 л.с." or "220 лс"
            r'\d+\s*hp',  # Engine power in hp
            r'\d+\s*kw',  # Engine power in kW
        ]
        
        mod_candidates = remaining_words[model_end_idx:]
        filtered_mods = []
        
        # Join the remaining words for easier pattern matching
        mod_text = ' '.join(mod_candidates)
        
        # Remove excluded patterns
        for pattern in exclude_patterns:
            mod_text = re.sub(pattern, '', mod_text, flags=re.IGNORECASE)
        
        # Clean up resulting string
        mod_text = re.sub(r'\s+', ' ', mod_text).strip()
        
        return brand, model, mod_text
    
    return brand, model, ""


def separate_trim_from_modifications(text: str) -> dict:
    """
    Separates trim level from other modifications.
    Returns a dictionary with 'trim' and 'modification' keys.
    """
    result = {}
    text = text.strip()
    
    if not text:
        return result
    
    # Trim words (usually appear as a distinct package name)
    trim_patterns = [
        r'(flagship|premium|luxury|sport|s-?line|m-?sport|avantgarde|amg|f-?sport|lounge|style|exclusive)',
        r'(edition|line|package|collection|limited)',
        r'(comfort|elegance|ambition|active|scout|rs|gt|fr)'
    ]
    
    # Find trim in the text
    trim = ""
    for pattern in trim_patterns:
        matches = re.finditer(pattern, text.lower())
        for match in matches:
            trim_match = match.group(0)
            if trim_match:
                trim = trim_match.upper()
                # Remove the trim from the text
                text = re.sub(re.escape(match.group(0)), '', text, flags=re.IGNORECASE)
                break
        if trim:
            break
    
    # Clean up remaining modifications
    modifications = re.sub(r'\s+', ' ', text).strip()
    
    # Exclude specific patterns from modifications
    exclude_patterns = [
        r'(?:\d+)?\s*(?:места|мест|seat(?:er|s)?)',  # Seating info
        r'\d+\s*(?:л\.?с\.?|hp|kw|ps)',              # Engine power
        r'[а-яА-Я]+',                                # Russian text (except for trim terms)
    ]
    
    # Remove excluded patterns from modifications
    for pattern in exclude_patterns:
        modifications = re.sub(pattern, '', modifications, flags=re.IGNORECASE)
    
    # Clean up again
    modifications = re.sub(r'\s+', ' ', modifications).strip()
    
    # Store results
    if trim:
        result["trim"] = trim
    
    if modifications:
        result["modification"] = modifications
    
    return result


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