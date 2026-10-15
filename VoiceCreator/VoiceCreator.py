import os
import re
import wave
import time
from piper.voice import PiperVoice

# Пути относительно директории VoiceCreator
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)

# Папка назначения Audios в корне проекта
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "Audios")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Модель и конфиг Piper
PIPER_MODEL = os.path.join(BASE_DIR, "ru_RU-denis-medium.onnx")
PIPER_CONFIG = os.path.join(BASE_DIR, "ru_RU-denis-medium.onnx.json")

# Модели RVC
RVC_MODEL = os.path.join(BASE_DIR, "VoiceJarvis.pth")
RVC_INDEX = os.path.join(BASE_DIR, "VoiceJarvis.index")

if not os.path.exists(PIPER_MODEL) or not os.path.exists(PIPER_CONFIG):
    print(f"[Ошибка]: Файлы Piper (.onnx / .json) не найдены в {BASE_DIR}")
    exit(1)

print("Загрузка Piper TTS...")
piper_voice = PiperVoice.load(PIPER_MODEL, config_path=PIPER_CONFIG)

# Проверка встроенной библиотеки RVC
HAS_RVC = False
try:
    from rvc_python.infer import RVCInference
    if os.path.exists(RVC_MODEL):
        print("Загрузка модели RVC (VoiceJarvis.pth)...")
        rvc = RVCInference(device="cuda:0")
        rvc.load_model(RVC_MODEL)
        if os.path.exists(RVC_INDEX):
            rvc.set_index(RVC_INDEX)
        HAS_RVC = True
except Exception:
    print("[Информация]: RVC библиотека не подключена напрямую в Python.")
    print("Файлы будут генерироваться через Piper TTS для прямой обработки в Applio Batch Inference.")

import numpy as np
from scipy.signal import butter, lfilter

def boost_bass_and_clarity(data, rate):
    """
    Усиливает низкие частоты (бас) и поднимает высокие (чёткость согласных Р, С, Т).
    """
    # 1. Усиление баса (Low-pass filter до 250 Гц)
    b_low, a_low = butter(2, 250 / (rate / 2), btype='low')
    bass = lfilter(b_low, a_low, data) * 1.8  # Множитель баса (1.8x)
    
    # 2. Усиление чёткости / верхов (High-pass filter от 2500 Гц)
    b_high, a_high = butter(2, 2500 / (rate / 2), btype='high')
    treble = lfilter(b_high, a_high, data) * 1.3  # Множитель чёткости (1.3x)
    
    # Смешиваем оригинальный звук с усиленным басом и верхами
    processed = data + bass + treble
    
    # Нормализация (чтобы не было хрипов и перегруза)
    max_val = np.max(np.abs(processed))
    if max_val > 0:
        processed = (processed / max_val) * 32767
        
    return processed.astype(np.int16)

def save_piper_wav(text: str, output_path: str):
    """Генерация с обработкой эквалайзера (бас + чёткость)"""
    temp_wav = output_path + "_raw.wav"
    
    # 1. Сначала генерируем сырой звук
    with wave.open(temp_wav, "wb") as wav_file:
        piper_voice.synthesize_wav(text, wav_file)
        
    # 2. Читаем и накладываем басы/чёткость
    with wave.open(temp_wav, "rb") as wav_in:
        rate = wav_in.getframerate()
        frames = wav_in.readframes(wav_in.getnframes())
        data = np.frombuffer(frames, dtype=np.int16)
        
    processed_data = boost_bass_and_clarity(data, rate)
    
    # 3. Сохраняем итоговый насыщенный файл
    with wave.open(output_path, "wb") as wav_out:
        wav_out.setnchannels(1)
        wav_out.setsampwidth(2)
        wav_out.setframerate(rate)
        wav_out.writeframes(processed_data.tobytes())
        
    if os.path.exists(temp_wav):
        os.remove(temp_wav)

def generate_jarvis_speech(text: str, filename: str):
    final_path = os.path.join(OUTPUT_DIR, filename)
    temp_path = os.path.join(OUTPUT_DIR, f"temp_{filename}")
    
    start_time = time.time()
    target_out = temp_path if HAS_RVC else final_path

    # 1. Быстрый синтез базового звука Piper
    save_piper_wav(text, target_out)
    print(f"1. Piper TTS сгенерировал базовый звук за {time.time() - start_time:.3f} сек.")

    # 2. Инференс RVC (если установлен rvc_python)
    if HAS_RVC:
        try:
            rvc_start = time.time()
            rvc.infer_file(
                input_path=temp_path,
                output_path=final_path,
                f0_up_key=0,
                f0_method="rmvpe"
            )
            if os.path.exists(temp_path):
                os.remove(temp_path)
            print(f"2. RVC обработал голос Джарвиса за {time.time() - rvc_start:.3f} сек.")
        except Exception as e:
            print(f"[Ошибка RVC]: {e}")
            if os.path.exists(temp_path):
                if os.path.exists(final_path):
                    os.remove(final_path)
                os.rename(temp_path, final_path)

    print(f">>> ГОТОВО! Сохранено: {final_path} (Всего: {time.time() - start_time:.3f} сек) <<<\n")

if __name__ == "__main__":
    print("\n=== ГЕНЕРАТОР ГОЛОСА ДЖАРВИСА ===")
    while True:
        phrase = input("Введите фразу (или 'exit' для выхода): ").strip()
        if phrase.lower() in ["exit", "quit", "выход"]:
            break
            
        if phrase:
            raw_num = input("Номер файла (1, 2, 3...): ").strip()
            
            clean_num = re.sub(r"\D", "", raw_num)
            if not clean_num:
                clean_num = "1"
            
            output_name = f"{clean_num}.wav"
            generate_jarvis_speech(phrase, output_name)