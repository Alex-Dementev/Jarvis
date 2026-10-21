import os
import json
import time
import random
import pygame
import sounddevice as sd
import vosk
import Commands
import Submission
from rapidfuzz import process, fuzz

# Инициализируем аудиоплеер
pygame.mixer.init()

MODEL_PATH = os.path.join("LanguageModels", "Language_Model_Ru")

print("Загрузка Vosk...")
model = vosk.Model(MODEL_PATH)
recognizer = vosk.KaldiRecognizer(model, 16000)

WAKE_WORDS = ["джарвис", "джервис", "жарвис", "Jarvis"]

RESPONSES = {
    1: "Да, сэр?",
    2: "Что сегодня, сэр?",
    3: "К вашим услугам, сэр!",
}

used_numbers = []
used_dont_numbers = []

STATE_WAITING_WAKE = "WAITING_WAKE"
STATE_LISTENING_CMD = "LISTENING_CMD"

current_state = STATE_WAITING_WAKE
last_speech_time = 0.0
command_buffer = []

is_speaking = False

def play_audio_file(file_path: str):
    global is_speaking

    if not os.path.exists(file_path):
        base, _ = os.path.splitext(file_path)
        file_path = f"{base}.mp3"

    if not os.path.exists(file_path):
        print(f"[Ошибка]: Файл {file_path} не найден!")
        return

    try:
        is_speaking = True
        pygame.mixer.music.load(file_path)
        pygame.mixer.music.play()
        
        while pygame.mixer.music.get_busy():
            time.sleep(0.05)
            
    except Exception as e:
        print(f"[Ошибка воспроизведения]: {e}")
    finally:
        is_speaking = False

def get_unique_random_number() -> int:
    available = [num for num in range(1, 4) if num not in used_numbers]
    chosen = random.choice(available)
    
    used_numbers.append(chosen)
    if len(used_numbers) > 1:
        used_numbers.pop(0)
        
    return chosen

def play_dont_response():
    available = [num for num in [1, 2] if num not in used_dont_numbers]
    chosen = random.choice(available)
    
    used_dont_numbers.append(chosen)
    if len(used_dont_numbers) > 1:
        used_dont_numbers.pop(0)
        
    file_path = os.path.join("Audios", "Dont", f"Dont{chosen}.wav")

    if(chosen == 1):
        print("ДЖАРВИС: Сэр, я не понимаю вас!\n")
    else:
        print("ДЖАРВИС: Моя твоя не понимать, сэр!\n")

    play_audio_file(file_path)

def play_audio_response(number: int):
    file_path = os.path.join("Audios", "Start", f"{number}.wav")
    play_audio_file(file_path)

def is_wake_word(text: str) -> bool:
    words = text.split()
    for word in words:
        best_match, score, _ = process.extractOne(word, WAKE_WORDS, scorer=fuzz.ratio)
        if score >= 70:
            return True
    return False

def clean_wake_words(text: str) -> str:
    words = text.split()
    cleaned = []
    for word in words:
        _, score, _ = process.extractOne(word, WAKE_WORDS, scorer=fuzz.ratio)
        if score < 70:
            cleaned.append(word)
    return " ".join(cleaned).strip()

def audio_callback(indata, frames, time_info, status):
    global current_state, last_speech_time, command_buffer, is_speaking

    if is_speaking:
        return

    bytes_data = bytes(indata)
    
    try:
        if recognizer.AcceptWaveform(bytes_data):
            result = json.loads(recognizer.Result())
            text = result.get("text", "").lower().strip()
        else:
            partial = json.loads(recognizer.PartialResult())
            text = partial.get("partial", "").lower().strip()
    except Exception as e:
        try:
            recognizer.Reset()
        except Exception:
            pass
        return

    if not text:
        return

    if current_state == STATE_WAITING_WAKE:
        if is_wake_word(text):
            num = get_unique_random_number()
            phrase = RESPONSES[num]
            print(f"\nДЖАРВИС: {phrase}\n")
            
            is_speaking = True 
            
            play_audio_response(num)
            
            recognizer.Reset()
            
            current_state = STATE_LISTENING_CMD
            last_speech_time = time.time() + 3.0
            command_buffer = []

    elif current_state == STATE_LISTENING_CMD:
        clean_text = clean_wake_words(text)
        if clean_text:
            last_speech_time = time.time()
            command_buffer = [clean_text]


print("\n=== Джарвис ===")

with sd.RawInputStream(samplerate=16000, blocksize=1000, dtype='int16', channels=1, callback=audio_callback):
    while True:
        if current_state == STATE_LISTENING_CMD:
            full_user_command = " ".join(command_buffer).strip() if command_buffer else ""
            word_count = len(full_user_command.split()) if full_user_command else 0
            
            pause_timeout = 0.35 if word_count < 4 else 0.5
            
            if time.time() - last_speech_time > pause_timeout:
                if command_buffer:
                    print(f"ВЫ: {full_user_command}\n")

                    is_handled = Commands.process_command(full_user_command)
    
                    if not is_handled:
                        Submission.process_submission(full_user_command, "")
                else:
                    play_dont_response()
                
                current_state = STATE_WAITING_WAKE
                command_buffer = []
                
                is_speaking = True
                recognizer.Reset()
                is_speaking = False
                
        time.sleep(0.05)