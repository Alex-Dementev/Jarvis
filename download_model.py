from faster_whisper import WhisperModel
import os

model_dir = os.path.join(os.path.dirname(__file__), "WhisperModel")

print("Скачиваю модель whisper-tiny...")
# Библиотека сама найдет и скачает всё нужное в папку WhisperModel
model = WhisperModel("tiny", device="cpu", compute_type="int8", download_root=model_dir)
print("Готово!")