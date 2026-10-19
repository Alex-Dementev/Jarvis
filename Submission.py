import base64
import io
import os
import time
import subprocess
from google import genai
from google.genai import types
from mss import mss
from PIL import Image
import pyautogui
from VoiceConverter import VoiceConverter

Voice = VoiceConverter()

KEY = ""
MODEL = "gemini-3.5-flash-lite"

max_images = 10
max_chars = 40000
max_user_info_chars = 10000

PROMPT_TEXT = (
    "You are Jarvis, the user's AI assistant. "
    "Core Behavior: "
    "- Keep answers extremely concise, direct, and to the point (1-2 sentences). "
    "- Do NOT use greetings, introductory phrases, or self-introductions unless explicitly asked. "
    "- Maintain a restrained, polite, and confident tone. "
    "- Do NOT output code or data structures in regular text responses. "
    "- Screen Analysis: Give precise instructions. If screen data is insufficient, directly ask the user to perform an action (e.g., scroll, switch tabs). Never guess. "
    "Output Structure (CRITICAL): "
    "You must strictly separate your output into the following blocks using these exact markers: "
    "1. $$response$$ [The text that will be synthesized/spoken to the user, ending with ', сэр!'] "
    "2. $$info$$ [New important facts about the user to save, or leave empty] ONLY THE MOST IMPORTANT ONES!!!"
    "3. $$shell$$ [Write full PowerShell commands here to control the PC. If no action is required, leave it empty]"
    "4. $$restart$$ [This is the same as '$$shell$$', but the response will be returned to you; use this to request data from the PC if necessary.]"
    "Strict Rules: "
    "- NEVER include the user's name before ', сэр!'. BAD: 'Привет, Алексей, сэр!' GOOD: 'Приветствую, сэр!' "
    "Forbidden commands: Shutting down device (except sleep mode), controlling the browser, closing Explorer."
)

client = genai.Client(api_key=KEY)


def update_user_info(about_user_path: str, new_fact: str):
  user_content = ""
  if os.path.exists(about_user_path):
    with open(about_user_path, "r", encoding="utf-8") as f:
      user_content = f.read()

  user_content += f"- {new_fact}\n"

  if len(user_content) > max_user_info_chars:
    user_content = user_content[-max_user_info_chars:]
    first_newline = user_content.find("\n")
    if first_newline != -1:
      user_content = user_content[first_newline + 1:]

  with open(about_user_path, "w", encoding="utf-8") as f:
    f.write(user_content)

def run_powershell(command: str) -> str:
    encoded = base64.b64encode(
        command.encode("utf-16le")
    ).decode("ascii")

    try:
        res = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-EncodedCommand",
                encoded
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60
        )

        output = (res.stdout or "").strip()
        errors = (res.stderr or "").strip()

        if res.returncode != 0:
            return f"Ошибка PowerShell (код {res.returncode}): {errors or output}"

        if errors:
            return f"Предупреждение PowerShell: {errors}\n{output}"

        return output or "Команда выполнена без текстового вывода."

    except subprocess.TimeoutExpired:
        return "Ошибка: превышено время выполнения команды."
    except Exception as e:
        return f"Ошибка запуска PowerShell: {e}"


def process_submission(text: str, extra_context: str = ""):
  if extra_context:
    full_user_input = f"{text}\nРезультат системного запроса: {extra_context}"
  else:
    full_user_input = text

  photos_lines, history_text, about_user_path = history_updater(text)

  user_info = ""
  if os.path.exists(about_user_path):
    with open(about_user_path, "r", encoding="utf-8") as f:
      user_info = f.read()

  contents = []

  full_context = (
      f"{PROMPT_TEXT}\n\n"
      f"О пользователе: {user_info}\n\n"
      f"История диалога:\n{history_text}"
      f"Текущее сообщение пользователя: {full_user_input}"
  )

  contents.append(full_context)

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

  try:
    response = client.models.generate_content(
        model=MODEL,
        contents=contents,
    )
    raw_answer = response.text.strip()
  except Exception as e:
    answer = "Произошла ошибка связи с сервером, сэр!"
    result_to_text(answer)
    return

  # --- НОВЫЙ УНИВЕРСАЛЬНЫЙ ПАРСИНГ ---
  answer_text = ""
  new_fact = ""
  shell_command = ""
  restart_command = ""

  print(raw_answer)

  # 1. Парсим $$response$$
  resp_tag = "$$response$$"
  if resp_tag in raw_answer:
    start_idx = raw_answer.find(resp_tag) + len(resp_tag)
    remaining = raw_answer[start_idx:]
    
    # Ищем следующий маркер '$$' для ограничения текста ответа
    next_dollar = remaining.find("$$")
    if next_dollar != -1:
      answer_text = remaining[:next_dollar].strip()
      remaining = remaining[next_dollar:]
    else:
      answer_text = remaining.strip()
      remaining = ""
  else:
    # Если модель забыла маркер response, считаем весь текст ответом
    answer_text = raw_answer

  # 2. По циклу парсим оставшиеся теги ($$info$$, $$shell$$, $$restart$$)
  while "@@" in remaining or "$$" in remaining:
    # Ищем ближайший тег
    if "$$info$$" in remaining:
      tag = "$$info$$"
    elif "$$shell$$" in remaining:
      tag = "$$shell$$"
    elif "$$restart$$" in remaining:
      tag = "$$restart$$"
    else:
      break

    start_idx = remaining.find(tag) + len(tag)
    remaining = remaining[start_idx:]
    
    # Ищем следующий разделитель $$
    next_dollar = remaining.find("$$")
    if next_dollar != -1:
      content = remaining[:next_dollar].strip()
      remaining = remaining[next_dollar:]
    else:
      # Больше знаков $$ нет — это конец строки, забираем всё до конца
      content = remaining.strip()
      remaining = ""

    # Распределяем по переменным в зависимости от найденного тега
    if tag == "$$info$$":
      new_fact = content
    elif tag == "$$shell$$":
      shell_command = content
    elif tag == "$$restart$$":
      restart_command = content

  # --- ОБРАБОТКА РЕЗУЛЬТАТОВ ---
  if new_fact:
    update_user_info(about_user_path, new_fact)

  if shell_command:
    try:
      res = run_powershell(shell_command)
      command_output = res.stdout if res.stdout else res.stderr
    except Exception as e:
      command_output = f"Ошибка: {e}"

  if answer_text:
    result_to_text(answer_text)

  if (restart_command and restart_command.strip() != 'powershell -Command ""'):
    try:
      res = run_powershell(restart_command)
      command_output = res.stdout if res.stdout else res.stderr
    except Exception as e:
      command_output = f"Ошибка: {e}"

    time.sleep(0.6)
    
    process_submission(text, command_output)


def result_to_text(result: str):
  script_dir = os.path.dirname(os.path.abspath(__file__))
  text_path = os.path.join(script_dir, "History", "History_Text.txt")
  if os.path.exists(text_path):
    with open(text_path, "r", encoding="utf-8") as f:
      content = f.read()

    content += f"ДЖАРВИС: {result}\n---\n"

    if len(content) > max_chars:
      content = content[-max_chars:]

    with open(text_path, "w", encoding="utf-8") as f:
      f.write(content)

  print(f"ДЖАРВИС: {result}\n")
  Voice.speak(result)


def create_screenshot() -> str:
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

    width, height = img.size
    new_size = (int(width / 1.0), int(height / 1.0))
    resized_img = img.resize(new_size, Image.Resampling.LANCZOS)

    buffer = io.BytesIO()
    resized_img.save(buffer, format="JPEG", quality=60)
    img_bytes = buffer.getvalue()

    return base64.b64encode(img_bytes).decode("utf-8")


def history_updater(reply_text: str):
  script_dir = os.path.dirname(os.path.abspath(__file__))
  history_dir = os.path.join(script_dir, "History")
  os.makedirs(history_dir, exist_ok=True)

  photos_path = os.path.join(history_dir, "History_Photos.txt")
  text_path = os.path.join(history_dir, "History_Text.txt")
  about_user_path = os.path.join(history_dir, "About_The_User.txt")
  img_b64 = create_screenshot()
  img_id = f"img_{int(time.time() * 1000)}"

  photos_lines = []
  if os.path.exists(photos_path):
    with open(photos_path, "r", encoding="utf-8") as f:
      photos_lines = f.readlines()

  new_photo_line = f"[{img_id}]: {img_b64}\n"
  photos_lines.append(new_photo_line)

  removed_img_ids = []
  if len(photos_lines) > max_images:
    excess = len(photos_lines) - max_images
    for _ in range(excess):
      old_line = photos_lines.pop(0)
      if "[" in old_line and "]" in old_line:
        start = old_line.find("[")
        end = old_line.find("]") + 1
        removed_img_ids.append(old_line[start:end])

  with open(photos_path, "w", encoding="utf-8") as f:
    f.writelines(photos_lines)

  new_text_entry = f"[{img_id}] Пользователь: {reply_text}\n"

  text_content = ""
  if os.path.exists(text_path):
    with open(text_path, "r", encoding="utf-8") as f:
      text_content = f.read()

  text_content += new_text_entry

  for r_id in removed_img_ids:
    text_content = text_content.replace(
        r_id, "[Удалено из за ограничений по колличеству]"
    )

  if len(text_content) > max_chars:
    text_content = text_content[-max_chars:]

  with open(text_path, "w", encoding="utf-8") as f:
    f.write(text_content)

  return photos_lines, text_content, about_user_path