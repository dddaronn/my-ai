import socket
import time
import json
import threading
import urllib.request
import urllib.error

# ======================= НАСТРОЙКИ =======================
# PC_IP = "auto"  -> телефон САМ находит ПК в USB-сети (ничего прописывать не надо, работает на любом ПК).
# PC_IP = "192.168.42.10" -> конкретный адрес ПК (если захочешь задать вручную).
PC_IP = "auto"
SUBNET = "192.168.42"   # префикс USB-сети Android (меняй, только если у тебя реально другой)
PC_PORT = 8080

# Облачный провайдер (запрос уходит ОТСЮДА, через мобильный интернет телефона).
BASE_URL = "https://moduleapi.pro/v1"
MODEL = "deepseek-v4-flash"
API_KEY = "sk-JLMlMKIWpjhCJ6OC2wjaki2hSlUuQz0FCnOKlCHm3dRRRAxQ"   # тот же рабочий ключ, что в api_key.txt на ПК


def ask_ai(question):
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
            return res["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        return f"Ошибка API ({e.code}): {e.read().decode('utf-8', 'ignore')}"
    except Exception as e:
        return f"Ошибка на телефоне: {e}"


def _connect_fixed():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(10)
    s.connect((PC_IP, PC_PORT))
    return s


def _connect_auto():
    # Сканируем всю подсеть параллельно и возвращаем сокет, подключённый к ПК
    # (тот адрес, который слушает PC_PORT). Если ПК сейчас не спрашивает — вернём None.
    result = {}
    lock = threading.Lock()

    def check(ip):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.4)
        try:
            if s.connect_ex((ip, PC_PORT)) == 0:
                with lock:
                    if "sock" not in result:
                        result["sock"] = s
                        return          # нашли ПК — держим этот сокет
                s.close()               # кто-то другой уже нашёл
            else:
                s.close()
        except Exception:
            try:
                s.close()
            except Exception:
                pass

    threads = [threading.Thread(target=check, args=(f"{SUBNET}.{i}",), daemon=True)
               for i in range(1, 255)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return result.get("sock")


def run_bridge():
    mode = "автопоиск ПК" if PC_IP == "auto" else f"ПК {PC_IP}"
    print(f"Телефон-мостик запущен ({mode}). Жду вопросы от ПК...")
    while True:
        try:
            sock = _connect_auto() if PC_IP == "auto" else _connect_fixed()
            if sock is None:
                time.sleep(1)           # ПК сейчас не спрашивает — пробуем снова
                continue
            with sock:
                sock.settimeout(120)
                question = sock.recv(4096).decode("utf-8")
                if question:
                    print(f"Вопрос от ПК: {question}")
                    answer = ask_ai(question)
                    sock.sendall(answer.encode("utf-8"))
                    print("Ответ отправлен.")
        except (ConnectionRefusedError, socket.timeout):
            time.sleep(1)
        except Exception as e:
            print(f"Ошибка соединения: {e}")
            time.sleep(1)


if __name__ == "__main__":
    run_bridge()
