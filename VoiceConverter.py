import os
import wave
import numpy as np
from scipy.signal import butter, lfilter
from piper.voice import PiperVoice
import sounddevice as sd
import soundfile as sf

# Определение пути к папке VoiceCreator
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VOICE_CREATOR_DIR = os.path.join(BASE_DIR, "VoiceCreator")

# Пути к файлам моделей внутри VoiceCreator
PIPER_MODEL = os.path.join(VOICE_CREATOR_DIR, "ru_RU-denis-medium.onnx")
PIPER_CONFIG = os.path.join(VOICE_CREATOR_DIR, "ru_RU-denis-medium.onnx.json")
RVC_MODEL = os.path.join(VOICE_CREATOR_DIR, "VoiceJarvis.pth")
RVC_INDEX = os.path.join(VOICE_CREATOR_DIR, "VoiceJarvis.index")


class VoiceConverter:
    def __init__(self):
        # 1. Загрузка Piper TTS
        if not os.path.exists(PIPER_MODEL) or not os.path.exists(PIPER_CONFIG):
            raise FileNotFoundError(
                f"[Ошибка]: Файлы Piper (.onnx / .json) не найдены по пути: {VOICE_CREATOR_DIR}"
            )

        print("[VoiceConverter]: Загрузка Piper TTS...")
        self.piper_voice = PiperVoice.load(PIPER_MODEL, config_path=PIPER_CONFIG)

        # 2. Инициализация RVC (если библиотека доступна)
        self.has_rvc = False
        try:
            from rvc_python.infer import RVCInference

            if os.path.exists(RVC_MODEL):
                print("[VoiceConverter]: Загрузка модели RVC (VoiceJarvis)...")
                self.rvc = RVCInference(device="cuda:0")
                self.rvc.load_model(RVC_MODEL)
                if os.path.exists(RVC_INDEX):
                    self.rvc.set_index(RVC_INDEX)
                self.has_rvc = True
        except Exception as e:
            print(f"[VoiceConverter Info]: RVC не используется/не доступен ({e}). Использование базового Piper TTS.")

    def _boost_bass_and_clarity(self, data: np.ndarray, rate: int) -> np.ndarray:
        """Усиливает низкие и высокие частоты."""
        # Низкие частоты (бас)
        b_low, a_low = butter(2, 250 / (rate / 2), btype='low')
        bass = lfilter(b_low, a_low, data) * 1.8

        # Высокие частоты (чёткость)
        b_high, a_high = butter(2, 2500 / (rate / 2), btype='high')
        treble = lfilter(b_high, a_high, data) * 1.3

        processed = data + bass + treble

        max_val = np.max(np.abs(processed))
        if max_val > 0:
            processed = (processed / max_val) * 32767

        return processed.astype(np.int16)

    def _generate_piper_wav(self, text: str, output_path: str):
        """Синтез аудио с помощью Piper и эквалайзера."""
        temp_raw = output_path + "_raw.wav"

        # Синтез сырого звука
        with wave.open(temp_raw, "wb") as wav_file:
            self.piper_voice.synthesize_wav(text, wav_file)

        # Обработка эквалайзером
        with wave.open(temp_raw, "rb") as wav_in:
            rate = wav_in.getframerate()
            frames = wav_in.readframes(wav_in.getnframes())
            data = np.frombuffer(frames, dtype=np.int16)

        processed_data = self._boost_bass_and_clarity(data, rate)

        with wave.open(output_path, "wb") as wav_out:
            wav_out.setnchannels(1)
            wav_out.setsampwidth(2)
            wav_out.setframerate(rate)
            wav_out.writeframes(processed_data.tobytes())

        if os.path.exists(temp_raw):
            os.remove(temp_raw)

    def speak(self, text: str, keep_file: bool = False):
        """
        Основной метод: принимает фразу, создает аудио и воспроизводит его.
        
        :param text: Текст для озвучки.
        :param keep_file: Сохранять ли итоговый .wav файл после воспроизведения.
        """
        if not text.strip():
            return

        temp_audio = os.path.join(VOICE_CREATOR_DIR, "temp_speech.wav")
        temp_rvc_input = os.path.join(VOICE_CREATOR_DIR, "temp_piper_out.wav")

        target_path = temp_rvc_input if self.has_rvc else temp_audio

        # 1. Генерация голоса через Piper TTS
        self._generate_piper_wav(text, target_path)

        # 2. Обработка RVC (при наличии)
        final_path = temp_audio
        if self.has_rvc:
            try:
                self.rvc.infer_file(
                    input_path=temp_rvc_input,
                    output_path=final_path,
                    f0_up_key=0,
                    f0_method="rmvpe"
                )
                if os.path.exists(temp_rvc_input):
                    os.remove(temp_rvc_input)
            except Exception as e:
                print(f"[Ошибка RVC]: {e}")
                final_path = temp_rvc_input

        # 3. Воспроизведение звука
        if os.path.exists(final_path):
            data, samplerate = sf.read(final_path)
            sd.play(data, samplerate)
            sd.wait()  # Ожидание окончания воспроизведения

            # Удаление временных файлов, если параметр keep_file=False
            if not keep_file and os.path.exists(final_path):
                os.remove(final_path)


# Пример использования метода:
if __name__ == "__main__":
    converter = VoiceConverter()
    converter.speak("Привет! Я готов воспроизвести любую вашу фразу.")