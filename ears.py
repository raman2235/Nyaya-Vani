import os
import pyaudio
import wave
from faster_whisper import WhisperModel

# 1. SYSTEM FIX: Explicit FFmpeg Path
ffmpeg_bin_path = r'C:\ffmpeg\bin' 
os.environ["PATH"] += os.pathsep + ffmpeg_bin_path

# 2. BILINGUAL GLOSSARY: Helps Whisper recognize names and legal terms
BILINGUAL_GLOSSARY = (
    "Jibangshu Paul, 32.11 lakhs, Case 0001, Section 27A, NDPS Act, "
    "ਜਿਬਾਂਗਸ਼ੂ ਪਾਲ, ਬੱਤੀ ਲੱਖ ਰੁਪਏ, ਮੁਲਜ਼ਮ, ਗਵਾਹ, ਜਮਾਨਤ"
)

def listen_and_transcribe():
    p = pyaudio.PyAudio()

    # STABILITY FIX: Auto-detect the correct hardware sample rate
    try:
        device_info = p.get_default_input_device_info()
        RATE = int(device_info['defaultSampleRate'])
        CHANNELS = 1
        CHUNK = 1024
        RECORD_SECONDS = 3 
        print(f"Hardware Detected: {device_info['name']} @ {RATE}Hz")
    except Exception as e:
        print(f"Could not find default microphone: {e}")
        return

    # 3. INITIALIZE FASTER-WHISPER (int8 for speed)
    print("Loading High-Speed Ear (Faster-Whisper)...")
    model = WhisperModel("small", device="cpu", compute_type="int8")

    # Open stream with hardware-matched RATE
    stream = p.open(format=pyaudio.paInt16, channels=CHANNELS, rate=RATE, 
                    input=True, frames_per_buffer=CHUNK)

    print("\n[LISTENING] Nyaya-Vani Ears Active (English/Punjabi)...")

    try:
        while True:
            frames = []
            # Buffer audio in 3-second intervals
            for _ in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
                # exception_on_overflow=False is critical for Windows stability
                data = stream.read(CHUNK, exception_on_overflow=False)
                frames.append(data)

            temp_file = "temp_witness_audio.wav"
            with wave.open(temp_file, 'wb') as wf:
                wf.setnchannels(CHANNELS)
                wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
                wf.setframerate(RATE)
                wf.writeframes(b''.join(frames))

            # 4. TRANSCRIPTION: High-Speed Segment Processing
            # Increased beam_size to 2 for better accuracy on names
            segments, info = model.transcribe(
                temp_file, 
                beam_size=2, 
                initial_prompt=BILINGUAL_GLOSSARY
            )
            
            # Combine segments into full text
            text = "".join([segment.text for segment in segments]).strip()
            detected_lang = info.language 

            # 5. GIBBERISH GUARD: Focus on English (en) and Punjabi (pa)
            if detected_lang in ['en', 'pa']:
                if text and len(text.split()) > 1:
                    print(f"[{detected_lang.upper()}] Witness: {text}")
            else:
                if text:
                    # Filter background static identified as other languages
                    print(f"[CLEANING] Ignored noise/other language: {detected_lang}")
            
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