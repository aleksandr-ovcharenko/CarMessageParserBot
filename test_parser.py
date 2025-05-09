import json
import re
from parser import parse_car_text

def test_emoji_format():
    test_messages = [
        """Доступен к покупке‼️
🔹Geely Coolray
    260T Battle
🔹Год: 10/2020
🔹Пробег: 35.000km
✅ Родная краска 
✅ Максималка
✅ Подогревы
⚙️ДВС: 1.5Т 177 л.с.
🔩Трансмиссия: DCT7
🛞Привод: Передний
💸Цена под ключ в РФ: 
    1.414.000 руб.""",
        
        """VIP минивэн от VW👍👍
‼️Доступен к покупке‼️
🔹Volkswagen Viloran
     Luxury Edition
🔹Год: 10/2021
🔹Пробег: 45.000km
✅ Родная краска 
⚙️ДВС: 2.0 TSI 190 л.с.
🔩Трансмиссия: DSG7
🛞Привод: Передний
💸Цена под ключ в РФ: 
     2.880.000 руб.""",
     
        """Автомобиль в наличии ( в Пути )❗️
👌Выкуплен нашей компанией и доступен к покупке!
🚗MERCEDES BENZ C CLASS 2016
⚙️ДВС: 1600сс бензин
⚙️Трансмиссия: АВТОМАТ
🛞Привод: Задний привод
✅Оценка: 4 балла
✅Пробег: 111.000км
✅Комплектация: C180 Coupe Sports +
💸Итоговая стоимость под ключ: 1.690.000₽""",

        """‼️Доступен к покупке‼️
🔹BYD 宋 Song Pro
    110Km Flagship Pro
🔹Год: 03/2022
🔹Пробег: 3.000Km!!!
✅ Родная краска 
✅ Максималка
✅ Как новая
✅ Автопилот
✅Подогревы
⚙️ДВС: 1.5 110 л.с.
🔋Установка 197 л.с.
🔩Трансмиссия:       Планетарка
🛞Привод: Передний
💸Цена под ключ в РФ: 
    1.736.000 руб.""",

        """Марка: Volkswagen Touareg
Модель: 2.0TSI R-Line (версия Ruiyi)
Год выпуска: октябрь 2020
Пробег: 65 000 км
Двигатель: 2.0T, 245 л.с., полный привод (4WD)
Дополнительно: отличное состояние, постоянный полный привод
Цена FOB Хоргос: $28.500 долларов США""",

        """Lynk&Co 09 MHEV 7 мест 

В НАЛИЧИИ в Москве новый автомобиль
Стоимость 5.100.000 с коммерческим утильсбором

Платформа SPA (на ней же VOLVO XC90)
Двигатель VEA (VOLVO ENGINE ARCHITECTURE)
Двигатель 2.0Т - 254 лс 
АКПП - 8ст автомат - AISIN
Полный привод - Haldex 
Бак - 70 литров
Средний расход по Москве 10,9 (проверено лично)
7 мест
МА - запуск двигателя с телефона
Есть лимитер - до 180 км/ч
Адаптивный круиз с удержанием в полосе - до 130 км/ч
Адаптивный круиз - до 150 км/ч"""
    ]
    
    # Специальный тест для Mercedes
    mercedes_line = "🚗MERCEDES BENZ C CLASS 2016"
    print("\nTesting Mercedes line extraction:")
    print(mercedes_line)
    # Очищаем строку от эмодзи и лишних символов
    clean_line = re.sub(r'[^\w\s]', ' ', mercedes_line).strip()
    print(f"Cleaned: '{clean_line}'")
    
    # Выделяем год, если он есть
    year_match = re.search(r'(20\d{2})', clean_line)
    if year_match:
        year = year_match.group(1)
        print(f"Found year: {year}")
        # Убираем год из строки
        clean_line = re.sub(r'20\d{2}', '', clean_line).strip()
        print(f"After year removal: '{clean_line}'")
    
    # Разбиваем строку на части для определения марки и модели
    print(f"Parts: {clean_line.split()}")
    
    print("\nTesting emoji format parser...")
    for i, message in enumerate(test_messages, 1):
        print(f"\n--- Test message {i} ---")
        print(message[:60] + "...")
        
        result, failed = parse_car_text(message, return_failures=True)
        
        print("\nParsed result:")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        
        if failed:
            print(f"\nFailed to parse: {', '.join(failed)}")
        else:
            print("\nNo parsing failures!")
            
        print("-" * 50)
    
    print("\nTesting completed!")

def test_lynk_format():
    """
    Специальный тест для формата Lynk & Co
    """
    test_message = """Lynk&Co 09 MHEV 7 мест 

В НАЛИЧИИ в Москве новый автомобиль
Стоимость 5.100.000 с коммерческим утильсбором

Платформа SPA (на ней же VOLVO XC90)
Двигатель VEA (VOLVO ENGINE ARCHITECTURE)
Двигатель 2.0Т - 254 лс 
АКПП - 8ст автомат - AISIN
Полный привод - Haldex 
Бак - 70 литров
Средний расход по Москве 10,9 (проверено лично)
7 мест
МА - запуск двигателя с телефона
Есть лимитер - до 180 км/ч
Адаптивный круиз с удержанием в полосе - до 130 км/ч
Адаптивный круиз - до 150 км/ч"""

    print("\nТестирование парсера для Lynk & Co\n")
    
    # Сначала пробуем прямой парсинг, минуя цепочку
    print("Direct lynk format test:")
    from parser import _try_lynk_format_parse
    brand_list = []
    result, failed = _try_lynk_format_parse(test_message, brand_list)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    # Затем полный парсинг через parse_car_text
    print("\nFull parsing chain test:")
    result, failed = parse_car_text(test_message, return_failures=True)
    
    print("Parsed result:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print()

    if failed:
        print(f"Failed to parse: {', '.join(failed)}")
    else:
        print("No parsing failures!")

    print("-" * 50)

def test_fob_price_usd():
    test_message = '''Бренд: Audi A8 (импорт)
Модель: A8L 50 TFSI quattro Premium Edition
Год выпуска: июнь 2022 года
Пробег: 35,000 км
Двигатель: 3.0T, 286 л.с., полный привод
Дополнительно: отличное состояние, постоянный полный привод
FOB Хоргос-цена: $52,300 долларов США'''
    result, failed = parse_car_text(test_message, return_failures=True)
    print("\nTest: FOB price USD\nInput:")
    print(test_message)
    print("\nParsed result:")
    import json
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if failed:
        print(f"Failed to parse: {', '.join(failed)}")
    else:
        print("No parsing failures!")
    print("-" * 50)

def test_price_with_dollar_emoji():
    test_message = '''Li 8 Pro
2023/07
Black/orange
Без зарядной станции, можно докупить отдельно за 450$
Машина в Хоргосе
Пробег 22.000км
Без окрасов
Цена 💲 34.500'''
    result, failed = parse_car_text(test_message, return_failures=True)
    print("\nTest: Price with dollar emoji\nInput:")
    print(test_message)
    print("\nParsed result:")
    import json
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if failed:
        print(f"Failed to parse: {', '.join(failed)}")
    else:
        print("No parsing failures!")
    print("-" * 50)

def test_audi_brand_model_extraction():
    test_message = '''Бренд: Audi A8 (импорт)
Модель: A8L 50 TFSI quattro Premium Edition'''
    result, failed = parse_car_text(test_message, return_failures=True)
    print("\nTest: Audi brand/model extraction\nInput:")
    print(test_message)
    print("\nParsed result:")
    import json
    print(json.dumps(result, ensure_ascii=False, indent=2))
    assert result.get("brand") == "Audi", f"Expected brand 'Audi', got {result.get('brand')}"
    assert result.get("model") == "A8", f"Expected model 'A8', got {result.get('model')}"
    print("Test passed!")
    print("-" * 50)

def test_li_auto_short_form():
    test_message = 'Li 8 Pro'
    result, failed = parse_car_text(test_message, return_failures=True)
    print("\nTest: Li Auto short form\nInput:")
    print(test_message)
    print("\nParsed result:")
    import json
    print(json.dumps(result, ensure_ascii=False, indent=2))
    assert result.get("brand") in ("Li Auto", "Li Xiang", "Li"), f"Expected brand 'Li Auto' or synonym, got {result.get('brand')}"
    assert result.get("model") == "8 Pro", f"Expected model '8 Pro', got {result.get('model')}"
    print("Test passed!")
    print("-" * 50)

def test_european_and_chinese_model_extraction():
    cases = [
        ("Марка: Mercedes-Benz S-Class (импорт)\nМодель: S 450 L 4MATIC", "Mercedes-Benz", "S-Class", "S 450 L 4MATIC"),
        ("Марка: Audi A6L\nМодель: 45 TFSI Premium Sport Edition", "Audi", "A6L", "45 TFSI Premium Sport Edition"),
        ("Марка: Porsche Cayenne (гибрид, новая энергия)\nМодель: Cayenne E-Hybrid 2.0T", "Porsche", "Cayenne", "Cayenne E-Hybrid 2.0T"),
        ("BMW X5 (импорт)", "BMW", "X5", ""),
        ("Mercedes Benz GLE350", "Mercedes-Benz", "GLE350", "")
    ]
    for i, (text, exp_brand, exp_model, exp_full_model) in enumerate(cases):
        print(f"\nTest case {i+1}:\nInput: {text}")
        result, failed = parse_car_text(text, return_failures=True)
        print("Parsed result:")
        import json
        print(json.dumps(result, ensure_ascii=False, indent=2))
        assert result.get("brand") == exp_brand, f"Expected brand '{exp_brand}', got {result.get('brand')}"
        assert exp_model in result.get("model", ""), f"Expected model to contain '{exp_model}', got {result.get('model')}"
        print("Test passed!")
        print("-" * 50)

def test_more_european_model_cases():
    cases = [
        ("Марка: BMW 4 Series\nМодель: 430i Gran Coupe M Sport Night Edition", "BMW", "4 Series", "430i Gran Coupe M Sport Night Edition"),
        ("Марка: BMW 7 Series (импорт)\nМодель: 735Li M Sport Package", "BMW", "7 Series", "735Li M Sport Package"),
        ("Марка: Mercedes-Benz E-Class\nМодель: E 300 2.0T (максимальная комплектация)", "Mercedes-Benz", "E-Class", "E 300 2.0T (максимальная комплектация)")
    ]
    for i, (text, exp_brand, exp_model, exp_full_model) in enumerate(cases):
        print(f"\nTest case (additional) {i+1}:\nInput: {text}")
        result, failed = parse_car_text(text, return_failures=True)
        print("Parsed result:")
        import json
        print(json.dumps(result, ensure_ascii=False, indent=2))
        assert result.get("brand") == exp_brand, f"Expected brand '{exp_brand}', got {result.get('brand')}"
        assert exp_model in result.get("model", ""), f"Expected model to contain '{exp_model}', got {result.get('model')}"
        print("Test passed!")
        print("-" * 50)

def test_brand_model_modification_format():
    """
    Test the improved parser with specific format: [Brand] [Model] [Modification]
    Examples provided by the user.
    """
    test_cases = [
        ("Mercedes-Benz E-Class E 300 2.0T Avantgarde", "Mercedes-Benz", "E-Class", "E 300 2.0T Avantgarde"),
        ("BMW X5 xDrive30d M Sport", "BMW", "X5", "xDrive30d M Sport"),
        ("Audi A6 45 TFSI quattro Sport", "Audi", "A6", "45 TFSI quattro Sport"),
        ("Toyota Camry 2.5L Prestige Safety", "Toyota", "Camry", "2.5L Prestige Safety"),
        ("Volkswagen Tiguan 2.0 TSI 4Motion R-Line", "Volkswagen", "Tiguan", "2.0 TSI 4Motion R-Line"),
        ("Lexus RX 350 AWD Luxury", "Lexus", "RX", "350 AWD Luxury"),
        ("Kia Sportage 2.0 MPI Luxe", "Kia", "Sportage", "2.0 MPI Luxe"),
        ("Hyundai Sonata 2.5 Smartstream Style", "Hyundai", "Sonata", "2.5 Smartstream Style"),
        ("Mazda CX-5 2.5 AWD Supreme", "Mazda", "CX-5", "2.5 AWD Supreme"),
        ("Porsche Macan 2.0T PDK Premium Plus", "Porsche", "Macan", "2.0T PDK Premium Plus"),
        ("Ford Explorer 3.0 EcoBoost Platinum", "Ford", "Explorer", "3.0 EcoBoost Platinum"),
        ("Volvo XC90 T6 AWD Inscription", "Volvo", "XC90", "T6 AWD Inscription"),
        ("Audi A5 (импорт) Sportback 40 TFSI Fashion Dynamic", "Audi", "A5", "Sportback 40 TFSI Fashion Dynamic"),

    ]
    
    print("\nTesting Brand Model Modification Format:\n")
    print("-" * 80)
    
    # Import the function to test from parser module
    from parser import improved_brand_model_parse, load_brand_list
    brand_list = load_brand_list()
    
    for i, (test_input, expected_brand, expected_model, expected_modification) in enumerate(test_cases, 1):
        print(f"Test case #{i}:")
        print(f"Input: {test_input}")
        
        brand, model, modifications = improved_brand_model_parse(test_input, brand_list)
        
        print(f"Expected: {expected_brand} / {expected_model} / {expected_modification}")
        print(f"Actual  : {brand} / {model} / {modifications}")
        
        if brand == expected_brand and model == expected_model and modifications == expected_modification:
            print("✅ Test passed!")
        else:
            print("❌ Test failed!")
            
            # Show which parts failed
            if brand != expected_brand:
                print(f"  Brand mismatch: expected '{expected_brand}', got '{brand}'")
            if model != expected_model:
                print(f"  Model mismatch: expected '{expected_model}', got '{model}'")
            if modifications != expected_modification:
                print(f"  Modification mismatch: expected '{expected_modification}', got '{modifications}'")
                
        print("-" * 80)
    
    print("Brand Model Modification Format testing completed!")

if __name__ == "__main__":
    test_emoji_format()
    test_lynk_format()
    test_fob_price_usd()
    test_price_with_dollar_emoji()
    test_audi_brand_model_extraction()
    test_li_auto_short_form()
    test_european_and_chinese_model_extraction()
    test_more_european_model_cases()
    test_brand_model_modification_format()
