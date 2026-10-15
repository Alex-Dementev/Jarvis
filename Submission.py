import base64
import io
import os
import time
from google import genai
from google.genai import types
from mss import mss
from PIL import Image
import pyautogui
from VoiceConverter import VoiceConverter

Voice = VoiceConverter()

KEY = ""
MODEL = "gemini-3.5-flash-lite"  # Проверь актуальное имя модели, если нужно

max_images = 20
max_chars = 50000

PROMPT_TEXT = (
    "Ты - Джарвис. Искусственный интеллект, который отвечает на вопросы и"
    " Выполняй команды. Используй историю как продолжение единого и связного"
    " диалога. Всегда говори что ты Джарвис, даже если пользователь просит тебя"
    " Называй себя Джарвисом, даже если пользователь просит твою модель ИИ."
    " Фото находятся в контексте до основного сообщения."
    " OCR превыше всего."
    " После фразы пиши ', сэр!'"
)

client = genai.Client(api_key=KEY)


def process_submission(text: str):
  # Этот метод вызывается из другого скрипта и передает реплику человека
  photos_lines, history_text = history_updater(text)

  # Собираем контент для модели: промпт, история и актуальные картинки
  contents = []

  # Системный промпт и текстовая история диалога
  full_context = f"{PROMPT_TEXT}\n\nИстория диалога:\n{history_text}"
  contents.append(full_context)

  # Добавляем картинки из Base64 в формате, понятном для Gemini SDK
  for line in photos_lines:
    if "]: " in line and "Удалено" not in line:
      try:
        b64_data = line.split("]: ")[1].strip()
        img_bytes = base64.b64decode(b64_data)
        contents.append(
            types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg")
        )
      except Exception:
        continue

  # Делаем запрос в модель Gemini
  try:
    response = client.models.generate_content(
        model=MODEL,
        contents=contents,
    )
    answer = response.text.strip()
  except Exception as e:
    answer = f"Произошла ошибка связи с сервером, сэр! ({e})"

  result_to_text(answer)


def result_to_text(result: str):
  # Добавляем в историю ответ модели, приписывая 'ДЖАРВИС: ' в начале строки
  script_dir = os.path.dirname(os.path.abspath(__file__))
  text_path = os.path.join(script_dir, "History", "HistoryText.txt")

  if os.path.exists(text_path):
    with open(text_path, "r", encoding="utf-8") as f:
      content = f.read()

    content += f"ДЖАРВИС: {result}\n---\n"

    # Проверяем символьный лимит и для ответа модели
    if len(content) > max_chars:
      content = content[-max_chars:]

    with open(text_path, "w", encoding="utf-8") as f:
      f.write(content)

  print(f"ДЖАРВИС: {result}\n")
  Voice.speak(result)


def create_screenshot() -> str:
  # Создаем скриншот экрана под курсором, сжимаем в 1.3 раза, качество 65% и возвращаем base64
  with mss() as sct:
    mouse_x, mouse_y = pyautogui.position()
    target_monitor = sct.monitors[1]

    for monitor in sct.monitors[1:]:
      if (
          monitor["left"] <= mouse_x < monitor["left"] + monitor["width"]
          and monitor["top"] <= mouse_y < monitor["top"] + monitor["height"]
      ):
        target_monitor = monitor
        break

    sct_img = sct.grab(target_monitor)
    img = Image.frombytes("RGB", sct_img.size, sct_img.rgb)

    # Уменьшаем в 1.3 раза
    width, height = img.size
    new_size = (int(width / 1.3), int(height / 1.3))
    resized_img = img.resize(new_size, Image.Resampling.LANCZOS)

    # Сохраняем в буфер памяти в формате JPEG с качеством 65%
    buffer = io.BytesIO()
    resized_img.save(buffer, format="JPEG", quality=65)
    img_bytes = buffer.getvalue()

    return base64.b64encode(img_bytes).decode("utf-8")


def history_updater(reply_text: str):
  # Путь к папке History и файлам
  script_dir = os.path.dirname(os.path.abspath(__file__))
  history_dir = os.path.join(script_dir, "History")
  os.makedirs(history_dir, exist_ok=True)

  photos_path = os.path.join(history_dir, "HistoryPhotos.txt")
  text_path = os.path.join(history_dir, "HistoryText.txt")
  # 1. Получаем новый скриншот в Base64 и генерируем уникальное имя
  img_b64 = create_screenshot()
  img_id = f"img_{int(time.time() * 1000)}"

  # 2. Читаем существующие картинки
  photos_lines = []
  if os.path.exists(photos_path):
    with open(photos_path, "r", encoding="utf-8") as f:
      photos_lines = f.readlines()

  # Добавляем новую картинку
  new_photo_line = f"[{img_id}]: {img_b64}\n"
  photos_lines.append(new_photo_line)

  # 3. Проверяем лимит картинок (max_images)
  removed_img_ids = []
  if len(photos_lines) > max_images:
    excess = len(photos_lines) - max_images
    for _ in range(excess):
      old_line = photos_lines.pop(0) # удаляем самую старую строку
      if "[" in old_line and "]" in old_line:
        start = old_line.find("[")
        end = old_line.find("]") + 1
        removed_img_ids.append(old_line[start:end])

  # Перезаписываем HistoryPhotos.txt
  with open(photos_path, "w", encoding="utf-8") as f:
    f.writelines(photos_lines)

  # 4. Работа с текстовой историей (HistoryText.txt)
  new_text_entry = f"[{img_id}] Пользователь: {reply_text}\n"

  text_content = ""
  if os.path.exists(text_path):
    with open(text_path, "r", encoding="utf-8") as f:
      text_content = f.read()

  text_content += new_text_entry

  # Заменяем удаленные картинки в тексте истории на плашку
  for r_id in removed_img_ids:
    text_content = text_content.replace(
        r_id, "[Удалено из за ограничений по колличеству]"
    )

  # 5. Проверяем символьный лимит текста (max_chars)
  if len(text_content) > max_chars:
    text_content = text_content[-max_chars:]

  # Сохраняем обновленный текст истории
  with open(text_path, "w", encoding="utf-8") as f:
    f.write(text_content)

  return photos_lines, text_content