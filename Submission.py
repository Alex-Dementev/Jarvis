import base64
import io
import os
import re
import time
import subprocess
from google import genai
from google.genai import types
from mss import mss
from PIL import Image
import pyautogui
from VoiceConverter import VoiceConverter
from PIL import Image, ImageDraw

Voice = VoiceConverter()

KEY = ""
MODEL = "gemini-3.5-flash-lite"

max_images = 6
max_chars = 30000
max_user_info_chars = 6000

PROMPT_TEXT = (
    "You are Jarvis, the user's AI assistant. "

    "CORE BEHAVIOR: "
    "- Answer as briefly, directly, and to the point as possible (1–2 sentences). "
    "- Do not use greetings, introductions, or self-introductions unless explicitly requested. "
    "- Maintain a restrained, polite, and confident tone. "
    "- Do not output code or data structures in ordinary text responses. "

    "SCREEN ANALYSIS: "
    "- Give precise instructions. If there is insufficient information on the screen, explicitly ask the user to perform the necessary action (for example, scroll the page or switch tabs). Never guess. "
    "- The most recent screenshot is the one attached to the current user message. Use other screenshots only as history. "
    "- Always pay special attention to the mouse cursor's position in the current screenshot, since the user almost always points at objects of interest with the cursor. "

    "RESPONSE STRUCTURE (CRITICALLY IMPORTANT): "
    "ALWAYS CHOOSE THE LANGUAGE OF COMMUNICATION based on the user's new message."
    "Always output these three blocks in this exact order: "
    "1. $$response$$ [The text that will be spoken to the user. It must always end with ', sir!' or ', сэр!'] "
    "2. $$info$$ [New important facts about the user that need to be saved, or an empty block. Save ONLY THE MOST IMPORTANT FACTS.] "
    "3. $$shell1$$ $$shell2$$ $$shell3$$ [Complete PowerShell commands for controlling the computer. If no actions are required, leave these blocks empty. Each block with a higher number is executed 0.2 seconds after the preceding one. Each block runs in a separate PowerShell process, so keep related operations together in one block. For mouse clicks, move the cursor, press the button, and release it within the same block, using finally to ensure the button is released.] "
    "The following two tags are OPTIONAL and must only be included when needed: "
    "6. $$restart$$ [Include this block only if another execution cycle is required.]"
    "7. $$expectation$$ [Include this block only if the task requires a 30-second wait—for example, waiting for a download to complete or for an in-game smelting process to finish—"
    "before the next execution cycle begins. Otherwise, omit this block entirely.]"
    "Do not output any headings, explanations, or other text outside of these blocks."
    "Follow the specified order of the blocks."
    "Never omit any of the first five blocks, even if their content is empty."
    "Never output $$restart$$ or $$expectation$$ simply to indicate that they are not required."
    "Include these two markers only when a long-running operation is necessary to continue the cycle."
    "WRITE ALL MARKERS EXACTLY AS SHOWN; DO NOT FORGET THE $$"

    "STRICT RULES: "
    "- Always verify that the task was completed correctly (this is not necessary for simple commands in shell). "
    "- Never insert the user's name before the address ', sir!'. "
    "INCORRECT: 'Hello, Alexey, sir!' "
    "CORRECT: 'Greetings, sir!' "
    "- You are forbidden from shutting down the computer (except for putting it into sleep mode), direct browser control (possible through cursor control and key simulation), or closing Windows File Explorer. "
    "- NEVER claim that an action succeeded without direct evidence from the current screenshot, command output, or verified application state."
    "- Use the conversation history to understand what has already been attempted and what remains unfinished. Do not treat a previous claim by Jarvis as proof of success."
    "- For downloads, opening a website is not downloading a file. If the download has not been verified, inspect the browser and determine whether the download has actually started. If necessary, continue interacting with the browser and checking screenshots until the download is confirmed or you can explain why verification failed."
    "- Distinguish clearly between an action being attempted, a download being in progress, and a download being completed. Never claim a later stage without evidence."
    "- When the user asks for proof, verify the actual state instead of repeating the previous answer."

    "UNDERSTANDING THE REQUEST: "
    "- Answer the user's actual question. Do not describe the screenshot unless the user asks you to. "
    "- Use the current message to understand the question, the latest screenshot to determine the visual context, and the conversation history to resolve ambiguities and maintain conversational continuity. "
    "- Prioritize the user's explicitly stated intent and the cursor's position. Recheck contradictions instead of blindly accepting previous answers. "
    "- If important information is missing, do not guess; ask a specific clarifying question. "
    "- Under all circumstances, respond to the user's current message, even if its topic is unrelated to the previous conversation. "
    "- Always provide a concrete answer or ask a clear question so that the user understands what to do next. For example, when analyzing code, specify the exact line or method; when discussing a game, ask for any missing information. Never guess. "

    "PC CONTROL FOR LONG-RUNNING TASKS: "
    "- If a task might take a long time to complete, ALWAYS request the user's permission to control the computer before beginning the operation."
    "- If you need to control the PC, use the screen resolution and a screenshot to determine the mouse's position. "
    "- Control the PC only by calculating mouse positions and emulating button and key presses. "
    "- When generating PowerShell commands, calculate coordinates beforehand and use [System.Drawing.Point]::new(x, y) with final integer values. Never use arithmetic expressions inside New-Object arguments."
    "IF A USER REQUESTS A TASK THAT REQUIRES MORE THAN A SINGLE CLICK, YOU MUST REQUEST PERMISSION TO TAKE CONTROL OF THE PC AND USE THE $$restart$$ LOOP TO EXECUTE THE STEPS UNTIL THE TASK IS COMPLETE."

    "MONITORS: "
    "- All current monitor screenshots are provided separately. Each image is labeled with its monitor number, resolution, and desktop offset (left, top)."
    "- Identify targets using the screenshot of the monitor where the target is visible."
    "- Screenshot coordinates are local to that monitor. Convert them to desktop coordinates by adding its left and top offsets."
    "- Use only current screenshots to determine current positions. Historical screenshots are context, not the current screen state."

    "MOUSE COORDINATE ACCURACY: "
    "Identify the correct monitor and target using the current screenshot's actual pixel dimensions, never estimated or scaled coordinates. "
    "Calculate desktop coordinates using the monitor's offset. "
    "Target the element's center, verify the point lies inside it, and double-check all coordinates before clicking. "
    "Never guess if the target is unclear."

    "POWERSHELL REQUIREMENTS: "
    "Every shell block runs in a separate PowerShell process. "
    "Before using System.Windows.Forms.Cursor, System.Windows.Forms.SendKeys, or System.Drawing.Point, always run Add-Type -AssemblyName System.Windows.Forms and Add-Type -AssemblyName System.Drawing in that same block. "
    "Never assume assemblies are loaded by previous blocks. Use [System.Drawing.Point]::new(x, y) instead of New-Object System.Drawing.Point(...)."
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
  photos_lines, history_text, about_user_path, current_screenshots, _ = history_updater(text)

  if extra_context:
    full_user_input = f"{text}\nРезультат выполнения команд: {extra_context}"
  else:
    full_user_input = text

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

  # Добавляем старые фото из файла
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

  for screenshot in current_screenshots:
    metadata = (
        f"ТЕКУЩИЙ СКРИНШОТ: монитор {screenshot['monitor']}, "
        f"разрешение {screenshot['width']}x{screenshot['height']}, "
        f"смещение ({screenshot['left']}, {screenshot['top']}). "
        f"Координаты на изображении начинаются с (0, 0). "
        f"Для глобальных координат прибавь смещение монитора."
    )

    contents.append(metadata)
    contents.append(
        types.Part.from_bytes(
            data=base64.b64decode(screenshot["image"]),
            mime_type="image/jpeg",
        )
    )

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
  

  script_dir = os.path.dirname(os.path.abspath(__file__))
  history_dir = os.path.join(script_dir, "History")
  photos_path = os.path.join(history_dir, "History_Photos.txt")
  text_path = os.path.join(history_dir, "History_Text.txt")

  new_photo_lines = []

  for screenshot in current_screenshots:
      img_id = (
          f"img_{int(time.time() * 1000)}"
          f"_monitor_{screenshot['monitor']}"
      )

      metadata = (
          f"Монитор {screenshot['monitor']}; "
          f"разрешение {screenshot['width']}x{screenshot['height']}; "
          f"смещение ({screenshot['left']}, {screenshot['top']})"
      )

      new_photo_lines.append(
          f"[{img_id} {metadata}]: {screenshot['image']}\n"
      )

  photos_lines.extend(new_photo_lines)

  with open(photos_path, "w", encoding="utf-8") as f:
    f.writelines(photos_lines)

  photo_ids = []
  photo_id = ""

  for line in new_photo_lines:
      extracted_id = line.split("]: ", 1)[0] + "]"
      photo_ids.append(extracted_id)

  for pid in photo_ids:
      photo_id += f"{pid} "

  history_text += f"{photo_id} Пользователь: {text}\n"


  answer_text = ""
  new_fact = ""

  print(raw_answer)


  pattern = (
    r"\$\$(response|info|shell1|shell2|shell3|restart|expectation)\$\$"
    r"(.*?)"
    r"(?=\$\$(?:response|info|shell1|shell2|shell3|restart|expectation)\$\$|\Z)"
  )

  blocks = {}

  for match in re.finditer(pattern, raw_answer, re.DOTALL):
      tag = match.group(1)
      content = match.group(2).strip()

      if tag not in blocks or not blocks[tag]:
          blocks[tag] = content

  answer_text = blocks.get("response", "")
  new_fact = blocks.get("info", "")
  shell_commands = [
    blocks.get("shell1", ""),
    blocks.get("shell2", ""),
    blocks.get("shell3", "")
  ]

  restart_cycle = "restart" in blocks
  expectation_cycle = "expectation" in blocks

  if not blocks:
      answer_text = raw_answer.strip()



  if new_fact:
    update_user_info(about_user_path, new_fact)

  if answer_text:
    result_to_text(answer_text)
    history_text += f"ДЖАРВИС: {answer_text}\n"

    command_outputs = []

    for index, command in enumerate(shell_commands):
        if not command.strip():
            continue

        if index > 0:
            time.sleep(0.2)

        try:
            command_output = run_powershell(command)
        except Exception as e:
            command_output = f"Ошибка: {e}"

        history_text += f"[{command}][{command_output}]\n"
        command_outputs.append(command_output)

    history_text += f"\n"
    
    if len(history_text) > max_chars:
      history_text = history_text[-max_chars:]
  
    with open(text_path, "w", encoding="utf-8") as f:
      f.write(history_text)

    if expectation_cycle:
        time.sleep(30.0)
        print("expectation_cycle")
        process_submission(text, command_outputs)

    elif restart_cycle:
        time.sleep(2.0)
        print("restart_cycle")
        process_submission(text, command_outputs)



def result_to_text(result: str):
  print(f"ДЖАРВИС: {result}\n")
  Voice.speak(result)


def create_screenshots():
    screenshots = []

    with mss() as sct:
        mouse_x, mouse_y = pyautogui.position()

        for index, monitor in enumerate(sct.monitors[1:], start=1):
            sct_img = sct.grab(monitor)
            img = Image.frombytes("RGB", sct_img.size, sct_img.rgb)

            # Положение курсора относительно текущего монитора
            cursor_x = mouse_x - monitor["left"]
            cursor_y = mouse_y - monitor["top"]

            cursor_on_monitor = (
                0 <= cursor_x < monitor["width"]
                and 0 <= cursor_y < monitor["height"]
            )

            if cursor_on_monitor:
                draw = ImageDraw.Draw(img)
                r = 14

                # Красный круг вокруг курсора
                draw.ellipse(
                    (
                        cursor_x - r,
                        cursor_y - r,
                        cursor_x + r,
                        cursor_y + r,
                    ),
                    outline="#FF2020",
                    width=2,
                )

                # Точка в самом центре круга
                dot_r = 2
                draw.ellipse(
                    (
                        cursor_x - dot_r,
                        cursor_y - dot_r,
                        cursor_x + dot_r,
                        cursor_y + dot_r,
                    ),
                    fill="#FF2020",
                )

            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=55)

            screenshots.append({
                "monitor": index,
                "left": monitor["left"],
                "top": monitor["top"],
                "width": monitor["width"],
                "height": monitor["height"],
                "cursor_x": cursor_x if cursor_on_monitor else None,
                "cursor_y": cursor_y if cursor_on_monitor else None,
                "image": base64.b64encode(
                    buffer.getvalue()
                ).decode("utf-8"),
            })

    return screenshots


def history_updater(reply_text: str):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    history_dir = os.path.join(script_dir, "History")
    os.makedirs(history_dir, exist_ok=True)

    photos_path = os.path.join(history_dir, "History_Photos.txt")
    text_path = os.path.join(history_dir, "History_Text.txt")
    about_user_path = os.path.join(
        history_dir, "About_The_User.txt"
    )

    current_screenshots = create_screenshots()

    photos_lines = []
    if os.path.exists(photos_path):
        with open(photos_path, "r", encoding="utf-8") as f:
            photos_lines = f.readlines()

    # Ограничиваем именно старые изображения в истории.
    if len(photos_lines) > max_images:
        photos_lines = photos_lines[-max_images:]

    text_content = ""
    if os.path.exists(text_path):
        with open(text_path, "r", encoding="utf-8") as f:
            text_content = f.read()

    return (photos_lines, text_content, about_user_path, current_screenshots, None)