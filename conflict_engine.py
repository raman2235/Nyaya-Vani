import os
import re
import sys
import time
import wave
import json
import queue
import threading
import pyaudio
import ollama
import pyttsx3
from faster_whisper import WhisperModel
from neo4j import GraphDatabase

# ==================================================================
# 1. HARDWARE & CLOUD CONFIGURATION ARCHITECTURE
# ==================================================================
AURA_URI = os.getenv("NEO4J_URI", "neo4j+s://bf8205a6.databases.neo4j.io")
AURA_AUTH = (os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "4Ax4dF6QE_6T19pOqQRnC_un0jYpQw6Cny5LS2kPozU"))

# Explicit FFmpeg path binding for Windows decoding stability
os.environ["PATH"] += os.pathsep + r'C:\ffmpeg\bin'

# Token vocabulary definitions to enforce precise naming recognition on Whisper layers
BILINGUAL_GLOSSARY = (
    "Nyaya-Vani court testimony validation check. Extract exact legal entities, "
    "accused names, IPC Sections, prior cases, clean records, section details, "
    "ਜਮਾਨਤ, ਮੁਲਜ਼ਮ, ਜਿਬਾਂਗਸ਼ੂ ਪਾਲ, ਰਾਜੇਸ਼ ਕੁਮਾਰ, ਪ੍ਰਿਆ ਸ਼ਰਮਾ, Priya Sharma, bail bond amount."
)

EXTRACTOR_PROMPT = """
Analyze the provided legal court testimony text. Extract structural legal facts as a raw JSON list of triples.
Strict Extraction Guidelines:
1. Identify the explicit person name as the "subject" dynamically from context.
2. Isolate the legal assertion as the "predicate" (e.g., 'charged_under', 'prior_convictions', 'bail_bond').
3. Isolate the qualitative status or value as the "object".
Format exactly: [{"subject": "NAME", "predicate": "RELATION", "object": "VALUE"}]
Output Rule: Return ONLY valid raw JSON array. No markdown wraps, no extra text notes.
"""

# Thread-safe global memory communications queue
audio_queue = queue.Queue()

# ==================================================================
# 2. ASYNC VOICE ALERT ENGINE
# ==================================================================
def speak_alert(message):
    def run_tts():
        try:
            engine = pyttsx3.init()
            engine.setProperty('rate', 155) 
            engine.say(message)
            engine.runAndWait()
        except: 
            pass
    threading.Thread(target=run_tts, daemon=True).start()

# ==================================================================
# 3. GRAPH DATABASE GROUND TRUTH CROSS-REFERENCE
# ==================================================================
def get_truth_from_graph(subject, predicate):
    try:
        sub_upper = str(subject).strip().upper()
        pred_lower = str(predicate).strip().lower()

        with GraphDatabase.driver(AURA_URI, auth=AURA_AUTH) as driver:
            with driver.session() as session:
                query = """
                MATCH (s:Entity)-[f:FACT]->(d:Detail)
                WHERE (toUpper(s.name) CONTAINS $sub OR $sub CONTAINS toUpper(s.name))
                  AND (toLower(f.predicate) CONTAINS $pred OR $pred CONTAINS toLower(f.predicate))
                RETURN d.value AS truth, f.case_ref AS case_ref
                """
                result = session.run(query, sub=sub_upper, pred=pred_lower)
                record = result.first()
                if record:
                    return record['truth'], record['case_ref']
    except Exception as e:
        pass
    return None, None

# ==================================================================
# 4. NATURAL LANGUAGE VERIFICATION PIPELINE
# ==================================================================
def process_and_verify(text):
    try:
        response = ollama.chat(model='llama3', messages=[
            {'role': 'system', 'content': EXTRACTOR_PROMPT},
            {'role': 'user', 'content': f"Live Testimony Text: {text}"}
        ])
        content = response['message']['content'].strip()
        
        json_match = re.search(r'\[.*\]', content, re.DOTALL)
        if not json_match:
            return

        live_triples = json.loads(json_match.group())
        
        for triple in live_triples:
            sub = triple.get('subject')
            pred = triple.get('predicate')
            obj = triple.get('object')
            
            if sub and pred and obj:
                print(f" 🔍 Evaluated Triples -> [{sub}] --({pred})--> [{obj}]")
                truth, case_ref = get_truth_from_graph(sub, pred)
                
                if truth:
                    if str(obj).lower().strip() != str(truth).lower().strip():
                        alert = f"Conflict detected! Accused {sub} claimed {obj}, but stored truth in Case reference {case_ref} confirms {truth}."
                        print(f"\n🚨🚨🚨 [ALARM STATUS] {alert}\n")
                        speak_alert(alert)
                    else:
                        print(f" ✅ [OK] Fact verified for {sub}. Matches database logs.")
    except Exception as e:
        pass

# ==================================================================
# 5. ASYNC AUDIO CONSUMER WORKER THREAD
# ==================================================================
def audio_processing_worker(model, channels, sample_size, rate):
    print("🧠 [BRAIN WORKER] Consumer Thread safely monitoring internal memory queue...")
    temp_process_file = "processing_chunk.wav"
    
    while True:
        frames = audio_queue.get()
        if frames is None:
            break
            
        with wave.open(temp_process_file, 'wb') as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(sample_size)
            wf.setframerate(rate)
            wf.writeframes(b''.join(frames))
            
        segments, info = model.transcribe(
            temp_process_file, 
            beam_size=5, 
            vad_filter=True,
            vad_parameters=dict(min_speech_duration_ms=400),
            initial_prompt=BILINGUAL_GLOSSARY
        )
        
        witness_text = " ".join([s.text for s in segments]).strip()
        
        if witness_text and len(witness_text.split()) > 1:
            lang_tag = str(info.language).upper()
            if info.language in ['en', 'pa']:
                print(f"\n🗣️ [{lang_tag}] Intercepted Speech: \"{witness_text}\"")
                process_and_verify(witness_text)
                
        audio_queue.task_done()

# ==================================================================
# 6. MASTER PRODUCER RUNTIME SYSTEM
# ==================================================================
def start_nyaya_vani():
    print("==================================================================")
    print("⚡ NYAYA-VANI: MASTER CONSOLIDATED REAL-WORLD ENGINE")
    print("==================================================================")
    print("📥 Loading Acoustic Decoding Weights (Faster-Whisper INT8 Engine)...")
    
    model = WhisperModel("small", device="cpu", compute_type="int8")
    p = pyaudio.PyAudio()
    
    try:
        device_info = p.get_default_input_device_info()
        CHANNELS = 1
        RATE = int(device_info['defaultSampleRate'])
        SAMPLE_SIZE = p.get_sample_size(pyaudio.paInt16)
        print(f"🟢 Active Audio Hardware Layer: {device_info['name']} @ {RATE}Hz")
    except Exception as e:
        print(f"❌ Input Microphone Registration Failure: {e}")
        p.terminate()
        return

    # Instantiating the async consumer thread parallel processing block
    worker_thread = threading.Thread(
        target=audio_processing_worker, 
        args=(model, CHANNELS, SAMPLE_SIZE, RATE), 
        daemon=True
    )
    worker_thread.start()

    stream = p.open(format=pyaudio.paInt16, channels=CHANNELS, rate=RATE, 
                    input=True, frames_per_buffer=1024)
    
    print("\n--- 🚀 MASTER PIPELINE RUNNING: LIVE CONTINUOUS STREAM LISTENING MODE ---")
    print("--- Speak your full multi-sentence legal statements fluidly without breaks ---\n")

    try:
        # 4-second sliding capture matrix window
        chunk_duration_seconds = 4.0 
        frames_per_chunk = int(RATE / 1024 * chunk_duration_seconds)
        
        while True:
            frames = []
            for _ in range(0, frames_per_chunk):
                data = stream.read(1024, exception_on_overflow=False)
                frames.append(data)
            
            # Non-blocking async queue assignment guarantees the microphone stream never drops
            audio_queue.put(frames)
            
    except KeyboardInterrupt:
        print("\n🛑 Nyaya-Vani master system safely shut down.")
    finally:
        stream.close()
        p.terminate()
        audio_queue.put(None)

if __name__ == "__main__":
    start_nyaya_vani()