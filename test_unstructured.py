import json
from parser import parse_car_text

def test_unstructured_specs():
    test_message = """Стоимость – 5 700 000 руб. 
(Коммерческий утиль)

Новый авто
2024 г.в.
Максимальная комплектация, рестайлинг!
555 лс
Полный привод
Параллельный гибрид (двигатель напрямую подключается к колесам через редуктор)
6 мест
Запас хода на чистом электричестве - 160км батарея 40 кВтч
Пневмоподвеска"""
    
    print("\nTesting unstructured specs parser...\n")
    print("--- Test message ---")
    print(test_message[:100] + "..." if len(test_message) > 100 else test_message)
    print()
    
    # Парсим сообщение
    result, failed = parse_car_text(test_message, return_failures=True)
    
    # Выводим результат в красивом JSON формате
    print("Parsed result:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print()
    
    # Проверяем и выводим информацию о неудачных полях
    if failed:
        print(f"Failed to parse: {', '.join(failed)}")
    else:
        print("No parsing failures!")
    
    print("-" * 50)

if __name__ == "__main__":
    test_unstructured_specs()
