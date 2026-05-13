# Worker для Windows Server 2003 (Python 3.4.4)

## Вимоги

- Windows Server 2003 SP2 або пізніше
- Python 3.4.4
- RabbitMQ доступен по мережі (не в Docker)

## Установка

1. Завантажте Python 3.4.4 з https://www.python.org/downloads/release/python-344/
2. Установіть Python (відмітьте "Add python.exe to Path")
3. Перевірте установку:

```cmd
python --version
```

4. Установіть залежності:

```cmd
cd windows_2003
pip install -r requirements.txt
```

## Конфігурація

Створіть `.env` файл у папці `windows_2003` з налаштуваннями:

```env
# RabbitMQ Configuration
RABBITMQ_DEFAULT_USER=guest
RABBITMQ_DEFAULT_PASS=guest
RABBITMQ_HOST=192.168.1.100
RABBITMQ_PORT=5672
RABBITMQ_QUEUE=events

# 1C Configuration
PATH_1C=C:\Program Files\1cv7
USER_1C=Administrator
PASS_1C=password
BRIDGE_VBS=C:\scripts\bridge.vbs
TEMP_DIR=C:\Temp
```

- Замініть `RABBITMQ_HOST` на IP-адресу вашого RabbitMQ сервера.
- Замініть `PATH_1C` на шлях до 1С:Підприємство на локальній машині.
- Замініть `USER_1C` і `PASS_1C` на облікові дані користувача 1С.
- Замініть `BRIDGE_VBS` на шлях до файла `bridge.vbs` (див. нижче).
- `TEMP_DIR` — папка для тимчасових файлів обміну (має існувати).

## Бізнес-логіка VBScript Bridge

Worker обробляє запити через VBScript мост до 1С:Підприємство:

1. **Отримання запиту** від RabbitMQ у форматі JSON (UTF-8)
2. **Створення тимчасового файлу** з payload у кодуванні **Windows-1251**
3. **Запуск VBScript** `bridge.vbs` з параметрами:
   - Шлях до вхідного JSON файлу
   - `PATH_1C` — шлях до 1С
   - `USER_1C` — користувач
   - `PASS_1C` — пароль
4. **Отримання результату** від `bridge.vbs` (шлях до файлу результату у win-1251)
5. **Перекодування результату** з Windows-1251 в UTF-8
6. **Відправка відповіді** через RabbitMQ клієнту

## Файл bridge.vbs

Ви маєте створити файл `bridge.vbs`, який:
- Приймає 4 параметри:
  - `inputFile` — шлях до вхідного JSON (win-1251)
  - `path1C` — шлях до 1С
  - `user1C` — користувач 1С
  - `pass1C` — пароль
- Читає вхідний JSON
- Підключається до 1С:Підприємство
- Виконує необхідну бізнес-логіку за даними з JSON
- Записує результат у новий JSON файл в кодуванні win-1251
- Повертає (виводить в stdout) повне ім'я файлу результату

Приклад структури `bridge.vbs`:

```vbscript
' bridge.vbs
Set args = WScript.Arguments
inputFile = args(0)
path1C = args(1)
user1C = args(2)
pass1C = args(3)

' Read input JSON from win-1251
Set FSO = CreateObject("Scripting.FileSystemObject")
Set inputFileObj = FSO.OpenTextFile(inputFile, 1, , -2)  ' -2 = ANSI (win-1251)
inputJSON = inputFileObj.ReadAll()
inputFileObj.Close()

' Parse and process input
' Connect to 1C and execute business logic...
' Create result JSON

' Write result to temporary file in win-1251
resultFile = FSO.GetSpecialFolder(2) & "\" & FSO.GetBaseName(inputFile) & "_result.json"
Set resultFileObj = FSO.CreateTextFile(resultFile, True, False)  ' False = ANSI (win-1251)
resultFileObj.Write resultJSON
resultFileObj.Close()

' Output the result file path
WScript.Echo resultFile
```

## Логи

Всі операції логуються в консоль з префіксом `[consumer]`:

```
[consumer] received: {'procedure': 'ping', ...}
[consumer] temp input file created: C:\Temp\tmp12345.json
[consumer] executing: cscript.exe bridge.vbs ...
[consumer] result file: C:\Temp\tmp12345_result.json
[consumer] result: {'status': 'ok', ...}
[consumer] response sent to results.uuid-xxx
[consumer] cleaned up input file: C:\Temp\tmp12345.json
[consumer] cleaned up output file: C:\Temp\tmp12345_result.json
```

## Запуск

Запустіть worker з командної строки:

```cmd
cd windows_2003
python consumer.py
```

Логи будуть виводитись у консоль.

## Запуск як Windows Service (опціонально)

Для автоматичного запуску worker як сервісу при завантаженні Windows:

1. Установіть pywin32:

```cmd
pip install pywin32
python Scripts/pywin32_postinstall.py -install
```

2. Створіть service wrapper (опціонально можна використати nssm)

## Бізнес-логіка

Основна обробка повідомлень знаходиться у функції `handle_message` у файлі `consumer.py`.

Змініть блок між коментарями:

```python
# --- Business logic goes here ---
response = {'status': 'ok', 'data': payload}
# --------------------------------
```

## Технічні особливості

- **Синхронний код** (не asyncio) — сумісний з Python 3.4
- **pika** замість aio-pika — синхронна бібліотека для RabbitMQ
- **Один потік** обробляє повідомлення послідовно (prefetch_count=1)
- **Стійкість до помилок** — при помилці повідомлення повертається в чергу

## Посилання

- RabbitMQ Management UI: http://RABBITMQ_HOST:15672
- Python 3.4 docs: https://docs.python.org/3.4/
- pika docs: https://pika.readthedocs.io/en/0.11.2/
