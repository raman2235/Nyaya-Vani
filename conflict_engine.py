import os
import re
import sys
import time
import wave
import json
import threading
import pyaudio
import ollama
import pyttsx3
from faster_whisper import WhisperModel
from neo4j import GraphDatabase

# --- ENVIRONMENTAL CORE CONFIGURATION ---
AURA_URI = os.getenv("NEO4J_URI", "neo4j+s://bf8205a6.databases.neo4j.io")
AURA_AUTH = (os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "4Ax4dF6QE_6T19pOqQRnC_un0jYpQw6Cny5LS2kPozU"))

os.environ["PATH"] += os.pathsep + r'C:\ffmpeg\bin'

# Broad system prompts instructing Whisper to catch diverse names and general structures cleanly
GENERAL_BILINGUAL_PROMPT = "Court testimony translation, legal terms, accused statement, IPC Section, case record verification."

# DYNAMIC PARSER: Instructs LLM to autonomously fish for any Subject, Predicate, and Object out of raw speech
EXTRACTOR_PROMPT = """
Analyze the provided legal witness or accused testimony text. Dynamically extract structural legal facts as a raw JSON list of triples.
Strict Extraction Guidelines:
1. Identify the explicit person/entity as the "subject" (Never hardcode; extract dynamically from context).
2. Isolate the legal assertion or charge as the "predicate" (e.g., 'charged_under', 'prior_convictions', 'bail_bond').
3. Isolate the qualitative status or metric value as the "object".
Format exactly: [{"subject": "DYNAMIC_NAME", "predicate": "RELATION", "object": "VALUE"}]
Output Rule: Return ONLY valid raw JSON array. Do not include markdown wraps or conversation notes.
"""

# --- NON-BLOCKING ASYNC VOICE ALERT LAYER ---
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

# --- DYNAMIC DATABASE ROUTINE ---
def get_truth_from_graph(subject, predicate):
    """Dynamically matches any given subject string against standard database nodes"""
    try:
        # Normalizing text cases to ensure robust lookup hits across database variations
        sub_upper = str(subject).strip().upper()
        pred_lower = str(predicate).strip().lower()

        with GraphDatabase.driver(AURA_URI, auth=AURA_AUTH) as driver:
            with driver.session() as session:
                # Flexible pattern matching lookup using CONTAINS criteria
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
        print(f"⚠️ Graph Query Resolution Error: {e}")
    return None, None

# --- CONTEXT VERIFICATION PIPELINE ---
def process_and_verify(text):
    try:
        response = ollama.chat(model='llama3', messages=[
            {'role': 'system', 'content': EXTRACTOR_PROMPT},
            {'role': 'user', 'content': f"Live Testimony Text: {text}"}
        ])
        content = response['message']['content'].strip()
        
        # Safe structural containment extraction regex to discard surrounding model chat logs
        json_match = re.search(r'\[.*\]', content, re.DOTALL)
        if not json_match:
            return

        live_triples = json.loads(json_match.group())
        
        for triple in live_triples:
            sub = triple.get('subject')
            pred = triple.get('predicate')
            obj = triple.get('object')
            
            if sub and pred and obj:
                print(f"🔍 Evaluated Semantic Triples -> [{sub}] --({pred})--> [{obj}]")
                
                # Dynamic matching execution pass
                truth, case_ref = get_truth_from_graph(sub, pred)
                
                if truth:
                    # Case-insensitive data serialization matching checks
                    if str(obj).lower().strip() != str(truth).lower().strip():
                        alert = f"Conflict detected! Accused {sub} claimed {obj}, but stored truth in Case reference {case_ref} confirms {truth}."
                        print(f"\n🚨🚨🚨 [ALARM] {alert}")
                        speak_alert(alert)
                    else:
                        print(f" ✅ [OK] Fact verified verified for {sub}. Statement matches verified database paths.")
    except Exception as e:
        print(f"⚠️ Analysis Engine Cycle Fault: {e}")

# --- STABLE HARDWARE SPEECH RUNTIME ENGINE ---
def start_nyaya_vani():
    print("==================================================================")
    print("⚡ NYAYA-VANI: FULLY DYNAMIC DUAL-DOMAIN VERIFICATION SYSTEM")
    print("==================================================================")
    print("📥 Loading Acoustic Decoding Matrix (Faster-Whisper INT8 Environment)...")
    model = WhisperModel("small", device="cpu", compute_type="int8")
    
    p = pyaudio.PyAudio()
    
    try:
        device_info = p.get_default_input_device_info()
        CHANNELS = 1
        RATE = int(device_info['defaultSampleRate'])
        print(f"🟢 Active Audio Interface Registered: {device_info['name']} @ {RATE}Hz")
    except Exception as e:
        print(f"❌ Input Hardware Streaming Missing: {e}")
        p.terminate()
        return

    stream = p.open(format=pyaudio.paInt16, channels=CHANNELS, rate=RATE, 
                    input=True, frames_per_buffer=1024)
    
    print("\n--- 🚀 NYAYA-VANI STREAM LIVE: SPEAK ANY TESTIMONY NAME & RECORD NOW ---")
    print("------------------------------------------------------------------")

    temp_file = "temp_live_testimony.wav"

    try:
        while True:
            frames = []
            # Optimized 3.8-second buffer window to cleanly ingest fluid compound statement phrasings
            for _ in range(0, int(RATE / 1024 * 3.8)): 
                data = stream.read(1024, exception_on_overflow=False)
                frames.append(data)

            with wave.open(temp_file, 'wb') as wf:
                wf.setnchannels(CHANNELS)
                wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
                wf.setframerate(RATE)
                wf.writeframes(b''.join(frames))

            segments, info = model.transcribe(temp_file, 
                                             beam_size=2, 
                                             initial_prompt=GENERAL_BILINGUAL_PROMPT)
            
            witness_text = " ".join([s.text for s in segments]).strip()
            
            if witness_text and len(witness_text.split()) > 2:
                lang_tag = str(info.language).upper()
                if info.language in ['en', 'pa']:
                    print(f"\n🗣️ [{lang_tag}] Intercepted Speech: \"{witness_text}\"")
                    process_and_verify(witness_text)
                else:
                    print(f" 🔇 Suppressed external background audio context signals: {lang_tag}")

    except KeyboardInterrupt:
        print("\n🛑 System safely shut down.")
    finally:
        stream.close()
        p.terminate()
        if os.path.exists(temp_file):
            os.remove(temp_file)

if __name__ == "__main__":
    start_nyaya_vani()