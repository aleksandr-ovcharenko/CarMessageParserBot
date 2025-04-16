import re


def clean_number(val):
    cleaned = re.sub(r"[^\d]", "", val)
    if not cleaned:
        print(f"[WARN] clean_number: пустое значение после очистки: {val}")
        return 0
    return int(cleaned)


def parse_car_text(text: str, return_failures=False):
    brand_list = load_brand_list()

    # Попробуем структурированный парсинг
    data, failed = _try_structured_parse(text, brand_list)

    if not data or data.get("brand") is None:
        # Попробуем fallback
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