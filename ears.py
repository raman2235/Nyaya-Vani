import os
import whisper
import pyaudio
import wave

# 1. SYSTEM FIX: Explicit FFmpeg Path
ffmpeg_bin_path = r'C:\ffmpeg\bin' 
os.environ["PATH"] += os.pathsep + ffmpeg_bin_path

# 2. BILINGUAL GLOSSARY: Anchors for English and Punjabi
# Includes key terms from your Knowledge Graph to prevent 'Henri Boot' errors
BILINGUAL_GLOSSARY = (
    "Jibangshu Paul, 32 lakhs, Case 0001, Section 27A, "
    "ਜਿਬਾਂਗਸ਼ੂ ਪਾਲ, ਬੱਤੀ ਲੱਖ ਰੁਪਏ, ਮੁਲਜ਼ਮ, ਗਵਾਹ, ਜਮਾਨਤ"
)

print("Loading the Ear (Whisper Model)...")
model = whisper.load_model("small")

def listen_and_transcribe():
    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 16000
    RECORD_SECONDS = 5 # 5-second bursts provide enough context for LangID

    p = pyaudio.PyAudio()
    stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, 
                    input=True, frames_per_buffer=CHUNK)

    print("\n[LISTENING] Speak in English or Punjabi...")

    try:
        while True:
            frames = []
            for _ in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
                data = stream.read(CHUNK)
                frames.append(data)

            temp_file = "temp_witness_audio.wav"
            with wave.open(temp_file, 'wb') as wf:
                wf.setnchannels(CHANNELS)
                wf.setsampwidth(p.get_sample_size(FORMAT))
                wf.setframerate(RATE)
                wf.writeframes(b''.join(frames))

            # 3. TRANSCRIPTION: Auto-detect with Strict Glossary
            result = model.transcribe(
                temp_file, 
                fp16=False, 
                language=None, # Auto-detect enabled
                initial_prompt=BILINGUAL_GLOSSARY 
            )
            
            # 4. GIBBERISH GUARD: Only allow English or Punjabi
            detected_lang = result.get('language', 'unknown')
            text = result['text'].strip()

            if detected_lang in ['en', 'pa']:
                print(f"[{detected_lang.upper()}] Witness: {text}")
            else:
                # If it hears noise and thinks it's another language, ignore it
                if text:
                    print(f"[CLEANING] Filtered out {detected_lang} noise.")
            
    except KeyboardInterrupt:
        print("\nStopping the Ears...")
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()
        if os.path.exists(temp_file):
            os.remove(temp_file)

if __name__ == "__main__":
    listen_and_transcribe()