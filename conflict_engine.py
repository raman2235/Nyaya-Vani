import os
import threading
import pyaudio
import wave
import ollama
import json
import pyttsx3
from faster_whisper import WhisperModel
from neo4j import GraphDatabase

# --- CONFIGURATION ---
AURA_URI = "neo4j+s://611cf5d1.databases.neo4j.io"
AURA_AUTH = ("neo4j", "wfvfnltMZNQcBJyUhjbTIa9yhXPA4GLyp44AyPbRvZs")

os.environ["PATH"] += os.pathsep + r'C:\ffmpeg\bin'

# STABILITY FIX: Help Whisper recognize your specific legal terms
BILINGUAL_PROMPT = "Jibangshu Paul, 32.11 lakhs, NDPS Act, Section 27A, Punjabi, English, court testimony."

EXTRACTOR_PROMPT = """
Analyze witness testimony and extract legal facts as JSON list of triples.
Rules: Only output JSON. Use "subject", "predicate", "object".
"""

# --- NON-BLOCKING VOICE ---
def speak_alert(message):
    def run_tts():
        try:
            engine = pyttsx3.init()
            engine.setProperty('rate', 160) 
            engine.say(message)
            engine.runAndWait()
        except: pass
    threading.Thread(target=run_tts, daemon=True).start()

# --- DATABASE LOGIC ---
def get_truth_from_graph(subject, predicate):
    try:
        with GraphDatabase.driver(AURA_URI, auth=AURA_AUTH) as driver:
            with driver.session() as session:
                query = """
                MATCH (e:Entity)-[f:FACT]->(d:Detail)
                WHERE e.name CONTAINS $sub AND f.type CONTAINS $pred
                RETURN d.value AS truth
                """
                result = session.run(query, sub=subject, pred=predicate)
                record = result.single()
                return record['truth'] if record else None
    except: return None

# --- NLP VERIFICATION ---
def process_and_verify(text):
    try:
        response = ollama.chat(model='llama3', messages=[
            {'role': 'system', 'content': EXTRACTOR_PROMPT},
            {'role': 'user', 'content': f"Testimony: {text}"}
        ])
        content = response['message']['content'].strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        
        live_triples = json.loads(content)
        for triple in live_triples:
            sub, pred, obj = triple.get('subject'), triple.get('predicate'), triple.get('object')
            if sub and pred:
                truth = get_truth_from_graph(sub, pred)
                if truth and str(obj).lower().strip() != str(truth).lower().strip():
                    alert = f"Conflict! {sub} said {obj}, but record shows {truth}."
                    print(f"\n[!!!] {alert}")
                    speak_alert(alert)
                elif truth:
                    print(f" [OK] Verified {sub}.")
    except: pass

# --- STABLE MAIN ENGINE ---
def start_nyaya_vani():
    print("Loading High-Speed Ear (Faster-Whisper)...")
    model = WhisperModel("small", device="cpu", compute_type="int8")
    
    p = pyaudio.PyAudio()
    
    # STABILITY FIX: Auto-detect correct hardware sample rate
    try:
        device_info = p.get_default_input_device_info()
        CHANNELS = 1
        RATE = int(device_info['defaultSampleRate'])
        print(f"Hardware Detected: {device_info['name']} @ {RATE}Hz")
    except Exception as e:
        print(f"Mic Error: {e}")
        return

    stream = p.open(format=pyaudio.paInt16, channels=CHANNELS, rate=RATE, 
                    input=True, frames_per_buffer=1024)
    
    print("\n--- NYAYA-VANI (STABLE MODE) ACTIVE ---")

    try:
        while True:
            frames = []
            # Optimization: 3-second recording window
            for _ in range(0, int(RATE / 1024 * 3)): 
                # exception_on_overflow=False prevents the Errno -9981 crash
                data = stream.read(1024, exception_on_overflow=False)
                frames.append(data)

            with wave.open("temp.wav", 'wb') as wf:
                wf.setnchannels(CHANNELS)
                wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
                wf.setframerate(RATE)
                wf.writeframes(b''.join(frames))

            # ACCURACY FIX: Added beam_size and initial_prompt
            segments, _ = model.transcribe("temp.wav", 
                                         beam_size=2, 
                                         initial_prompt=BILINGUAL_PROMPT)
            
            witness_text = " ".join([s.text for s in segments]).strip()
            
            if witness_text and len(witness_text.split()) > 2:
                print(f"Witness: {witness_text}")
                process_and_verify(witness_text)

    except KeyboardInterrupt:
        print("\nShutdown.")
    finally:
        stream.close()
        p.terminate()

if __name__ == "__main__":
    start_nyaya_vani()