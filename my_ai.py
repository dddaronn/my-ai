import json
import os
import pathlib
import socket
import sys
import urllib.request
import urllib.error

# Чтобы вывод русского текста и эмодзи не падал в консоли Windows.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# ======================= НАСТРОЙКИ =======================
# False  -> ПК сам ходит в интернет (нужен интернет у ПК, сайт не заблокирован)
# True   -> запрос идёт через телефон-мостик (phone_bridge.py на телефоне)
USE_PHONE = False

# Провайдер (OpenAI-совместимый). Используется только в прямом режиме (USE_PHONE = False).
BASE_URL = "https://moduleapi.pro/v1"
MODEL = "deepseek-v4-flash"

# Порт, на котором ПК ждёт телефон-мостик (режим USE_PHONE = True)
PHONE_PORT = 8080

# Ключ (нужен только в прямом режиме): из переменной окружения AI_API_KEY,
# либо из файла api_key.txt — сначала в папке запуска, потом рядом с библиотекой.
API_KEY = os.getenv("AI_API_KEY", "").strip()
if not API_KEY:
    for _p in (pathlib.Path.cwd() / "api_key.txt",
               pathlib.Path(__file__).with_name("api_key.txt")):
        if _p.exists():
            API_KEY = _p.read_text(encoding="utf-8").strip()
            break


def ask(question):
    if USE_PHONE:
        return _ask_via_phone(question)
    return _ask_direct(question)


def _ask_direct(question):
    if not API_KEY:
        print("Нет ключа. Вставь свой ключ в файл api_key.txt рядом со скриптом.")
        return

    data = {"model": MODEL, "messages": [{"role": "user", "content": question}]}
    req = urllib.request.Request(
        f"{BASE_URL}/chat/completions",
        data=json.dumps(data).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            res = json.loads(r.read().decode("utf-8"))
            answer = res["choices"][0]["message"]["content"]
            print(answer)
            return answer
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")
        print(f"Ошибка API ({e.code}): {body}")
    except Exception as e:
        print(f"Ошибка: {e}")


def _ask_via_phone(question):
    # ПК становится сервером и ждёт, пока телефон-мостик подключится сам.
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(("0.0.0.0", PHONE_PORT))
            server.listen(1)
            server.settimeout(30)
            print("Жду телефон-мостик...")

            conn, _addr = server.accept()
            with conn:
                conn.settimeout(120)
                conn.sendall(question.encode("utf-8"))

                # Читаем ответ до закрытия соединения телефоном (ответ может быть длинным).
                chunks = []
                while True:
                    part = conn.recv(4096)
                    if not part:
                        break
                    chunks.append(part)
                answer = b"".join(chunks).decode("utf-8")
                print(answer)
                return answer
    except socket.timeout:
        print("Телефон-мостик не подключился за 30 сек. "
              "Запущен ли phone_bridge.py на телефоне? Верный ли IP ПК в нём?")
    except Exception as e:
        print(f"Ошибка: {e}")
