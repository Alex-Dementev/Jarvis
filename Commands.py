import ctypes
import base64
from datetime import datetime
import os
import shutil
import subprocess
import time
import GPUtil
import psutil
import pygame
from VoiceConverter import VoiceConverter
from datetime import datetime

try:
    import screen_brightness_control as sbc

    HAS_BRIGHTNESS = True
except Exception:
    HAS_BRIGHTNESS = False

try:
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

    HAS_VOLUME = True
except Exception:
    HAS_VOLUME = False

SOUNDS_DIR = os.path.join("Audios", "LocalCommands")

Voice = VoiceConverter()

current_sound = 0

def play_sound(sound_name: str, wait_to_finish: bool = True) -> bool:
    possible_extensions = ["", ".wav"]
    file_path = None
    for ext in possible_extensions:
        temp_path = os.path.join(SOUNDS_DIR, f"{sound_name}{ext}")
        if os.path.exists(temp_path):
            file_path = temp_path
            break
    if not file_path:
        print(f"[Ошибка]: Звук '{sound_name}' не найден в {SOUNDS_DIR}")
        return False
    try:
        pygame.mixer.music.load(file_path)
        pygame.mixer.music.play()
        if wait_to_finish:
            while pygame.mixer.music.get_busy():
                time.sleep(0.05)
        return True
    except Exception as e:
        print(f"[Ошибка воспроизведения {file_path}]: {e}")
        return False
    
try:
    import pynvml
    pynvml.nvmlInit()
    HAS_GPU_MONITOR = True
except Exception:
    HAS_GPU_MONITOR = False

def plural_form(number, singular_nom, singular_gen, plural_gen):
    n = abs(number) % 100
    n1 = n % 10
    if 10 < n < 20:
        return plural_gen
    if 1 < n1 < 5:
        return singular_gen
    if n1 == 1:
        return singular_nom
    return plural_gen

def run_powershell(command: str) -> str:
    encoded = base64.b64encode(command.encode("utf-16le")).decode("ascii")
    try:
        res = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10
        )
        return (res.stdout or "").strip()
    except Exception as e:
        return f"Ошибка: {e}"

def change_volume_ps(direction: str, steps: int = 3):
    key_code = 175 if direction == "up" else 174
    script = f"$obj = New-Object -ComObject WScript.Shell; for($i=0; $i -lt {steps}; $i++){{$obj.SendKeys([char]{key_code})}}"
    run_powershell(script)

def change_brightness_ps(step: int):
    if(step == 1):
        run_powershell("(Get-WmiObject -Namespace root\WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1, 100)")
    else:
        run_powershell("(Get-WmiObject -Namespace root\WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1, 0)")

def get_system_status() -> str:
    cpu_usage = int(psutil.cpu_percent(interval=0.5))
    ram_usage = int(psutil.virtual_memory().percent)
    status_text = f"Процессор загружен на {cpu_usage} процентов. Оперативная память заполнена на {ram_usage} процентов."
    gpu_usage = None
    try:
        gpus = GPUtil.getGPUs()
        if gpus:
            gpu_usage = int(gpus[0].load * 100)
    except Exception:
        pass
    if gpu_usage is None:
        try:
            pynvml.nvmlInit()
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            utilization = pynvml.nvmlDeviceGetUtilizationRates(handle)
            gpu_usage = int(utilization.gpu)
        except Exception:
            pass
    if gpu_usage is not None:
        if(gpu_usage in [1, 21, 31, 41, 51, 61, 71, 81, 91]):
            status_text += f" Видеокарта загружена на {gpu_usage} процент."
        elif(gpu_usage in [2, 3, 4]):
            status_text += f" Видеокарта загружена на {gpu_usage} процента."
        else:
            status_text += f" Видеокарта загружена на {gpu_usage} процентов."
    else:
        status_text += " Данные о видеокарте недоступны."
    return status_text

MONTHS_RU = {1: "январь", 2: "февраль", 3: "март", 4: "апрель", 5: "май", 6: "июнь", 7: "июль", 8: "август", 9: "сентябрь", 10: "октябрь", 11: "ноябрь", 12: "декабрь"}

def get_free_space(drive_letter: str = "C") -> int:
    clean_letter = drive_letter.rstrip(":\\/")
    drive = f"{clean_letter}:\\"
    free_bytes = shutil.disk_usage(drive).free
    return free_bytes // (1024**3)

def process_command(text: str) -> bool:
    text_lower = text.lower()
    
    words = text_lower.split()
    word_count = len(words)

    if word_count > 6: 
        unknown_command()
        return False




    if "открой" in text_lower and word_count < 4 or "запусти" in text_lower and word_count < 4:
        if "калькулятор" in text_lower:
            print("ДЖАРВИС: Калькулятор запущен, сэр!")
            subprocess.Popen("calc.exe")
            play_sound("calculator_opened")
            return True
        elif "командную строку" in text_lower:
            print("ДЖАРВИС: Командная строка запущена, сэр!")
            subprocess.Popen("start cmd.exe", shell=True)
            play_sound("command_prompt_opened")
            return True
        elif "диспетчер задач" in text_lower:
            print("ДЖАРВИС: Диспетчер задач запущен, сэр!")
            ctypes.windll.shell32.ShellExecuteW(None, "runas", "taskmgr.exe", None, None, 1)
            play_sound("taskmgr_opened")
            return True
        

    if "закрой" in text_lower and word_count < 4 or "выключи" in text_lower and word_count < 4:
        if "калькулятор" in text_lower:
            print("ДЖАРВИС: Калькулятор закрыт, сэр!")
            subprocess.run("taskkill /f /im CalculatorApp.exe", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run("taskkill /f /im calc.exe", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            play_sound("calculator_closed")
            return True
        elif "командную строку" in text_lower:
            print("ДЖАРВИС: Командная строка закрыта, сэр!")
            subprocess.run("taskkill /f /im cmd.exe", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            play_sound("command_prompt_closed")
            return True
        elif "диспетчер задач" in text_lower:
            print("ДЖАРВИС: Диспетчер задач закрыт, сэр!")
            subprocess.run('powershell -command "Stop-Process -Name Taskmgr -Force"', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            play_sound("taskmgr_closed")
            return True
    

    if(("спасибо" in text_lower or "благoдарю" in text_lower) and word_count < 5):
        print("ДЖАРВИС: Всегда рад помочь, сэр!\n")
        play_sound("reach_again")
        return True

    if("молодец" in text_lower or "хорошо" in text_lower or "отлично" in text_lower):
        print("ДЖАРВИС: Спасибо, сэр!\n")
        play_sound("thanks")
        return True
    

    if "точное время" in text_lower and word_count < 5:
        now = datetime.now()
        h_str = f"{now.hour} {plural_form(now.hour, 'час', 'часа', 'часов')}"
        m_str = f"{now.minute} {plural_form(now.minute, 'минута', 'минуты', 'минут')}"
        s_str = f"{now.second} {plural_form(now.second, 'секунда', 'секунды', 'секунд')}"
        print(f"ДЖАРВИС: Сейчас {h_str}, {m_str}, и {s_str}, Сэр!\n")
        Voice.speak(f"Сейчас {h_str}, {m_str}, и {s_str}, Сэр!")
        return True

    elif "время" in text_lower or "который час" in text_lower and word_count < 4:
        now = datetime.now()
        h_str = f"{now.hour} {plural_form(now.hour, 'час', 'часа', 'часов')}"
        m_str = f"{now.minute} {plural_form(now.minute, 'минута', 'минуты', 'минут')}"
        print(f"ДЖАРВИС: Сейчас {h_str}, {m_str}, Сэр!\n")
        Voice.speak(f"Сейчас {h_str}, {m_str}, Сэр!")
        return True

    elif "дата" in text_lower and word_count < 4:
        now = datetime.now()
        month_name = MONTHS_RU[now.month]
        print(f"ДЖАРВИС: Сегодня {month_name}, {now.day} число, Сэр!\n")
        Voice.speak(f"Сегодня {month_name}, {now.day}ое число, Сэр!")
        return True


    if word_count < 4:
        if (("состоян" in text_lower or "груз" in text_lower) and ("систем" in text_lower or "ноутбук" in text_lower or "компьютер" in text_lower)):
            status_info = get_system_status()
            print(f"ДЖАРВИС: {status_info}")
            Voice.speak(status_info)
            return True


    if word_count < 5:
        if "спящий режим" in text_lower or "засни" in text_lower:
            print(f"ДЖАРВИС: Отключаю. До связи, Сэр!\n")
            play_sound("sleep_mode_1")
            ctypes.windll.PowrProf.SetSuspendState(0, 0, 0)
            return True
        elif ("покойн" in text_lower and "ноч" in text_lower):
            print(f"ДЖАРВИС: Дристать вам пол ночи, Сэр!\n")
            play_sound("sleep_mode_2")
            ctypes.windll.PowrProf.SetSuspendState(0, 0, 0)
            return True

        if word_count < 6:
            if ("мест" in text_lower and "на" in text_lower and "диск" in text_lower):
                free_gbC = get_free_space("C")
                free_gbD = get_free_space("D")
                print(f"ДЖАRВИС: На диске C: свободно {free_gbC} гигабайт. На диске D: свободно {free_gbD} гигабайт.")
                Voice.speak(f"На диске C: свободно {free_gbC} гигабайт. На диске D: свободно {free_gbD} гигабайт.")
                return True


    if ("громче" in text_lower or "прибавь звук" in text_lower or ("увел" in text_lower and "гром" in text_lower) or ("увел" in text_lower and "звук" in text_lower) or ("больш" in text_lower and "звук" in text_lower)) and word_count < 5:
        print("ДЖАРВИС: Делаю громче, сэр!")
        change_volume_ps("up", steps=5)
        play_sound("volume_up")
        return True

    if ("тише" in text_lower or "убавь звук" in text_lower or ("умен" in text_lower and "гром" in text_lower) or ("умен" in text_lower and "звук" in text_lower)) and word_count < 5:
        print("ДЖАРВИС: Делаю тише, сэр!")
        change_volume_ps("down", steps=5)
        play_sound("volume_down")
        return True

    if (("днев" in text_lower and "режим" in text_lower) or ("ярк" in text_lower and "режим" in text_lower) or ("ярк" in text_lower and "макс" in text_lower)) and word_count < 5:
        print("ДЖАРВИС: Увеличиваю яркость, сэр!")
        change_brightness_ps(1)
        play_sound("brightness_up")
        return True

    if (("ноч" in text_lower and "режим" in text_lower) or ("ярк" in text_lower and "миним" in text_lower) or ("темн" in text_lower and "режим" in text_lower)) and word_count < 5:
        print("ДЖАРВИС: Уменьшаю яркость, сэр!")
        change_brightness_ps(0)
        play_sound("brightness_down")
        return True


    if ("крой" in text_lower or "закрой" in text_lower or "сверни" in text_lower) and "окн" in text_lower and word_count < 5:
        print("ДЖАРВИС: Сворачиваю все окна, сэр!")
        subprocess.run(
            'powershell -command "(New-Object -ComObject Shell.Application).ToggleDesktop()"',
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        play_sound("windows_minimized")
        return True


    isBadWord = any(bad_word in text_lower for bad_word in ["тупой", "идиот", "дурак", "глупый", "тупица", "тупая", "идиотка", "дура", "глупая", "сука", "сволочь", "мерзавец", "мерзавка", "тварь", "блядь", "пидор", "даун", "лох", "козёл", "козлина", "задолбал", "мудак", "мудачка", "заебал", "заебала", "пидорас", "заколебался", "умри"])
    if isBadWord and word_count < 4:
        if("ты" in text_lower or "вы" in text_lower):
            print("ДЖАРВИС: Это очень тонкое замечание, сэр!\n")
            play_sound("bad_words_you")
        elif("я" in text_lower):
            print("ДЖАРВИС: Поздравляю, сэр!\n")
            play_sound("bad_words_me")
        return True


    
    unknown_command()
    return False


def unknown_command():
    global current_sound
    if current_sound == 0:
        play_sound("unknown_command_1")
        print("ДЖАРВИС: Мне нужно подумать, сэр!\n")
        current_sound = 1
    else:
        play_sound("unknown_command_2")
        print("ДЖАРВИС: Дайте мне подумать, сэр!\n")
        current_sound = 0