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

if __name__ == "__main__":
    test_emoji_format()
    test_lynk_format()
    test_fob_price_usd()
    test_price_with_dollar_emoji()
