import os
import whisper
import pyaudio
import wave
import ollama
import json
from neo4j import GraphDatabase

# --- CONFIGURATION ---
# Use your Neo4j Aura credentials
AURA_URI = "neo4j+s://611cf5d1.databases.neo4j.io"
AURA_AUTH = ("neo4j", "YOUR_ACTUAL_AURA_PASSWORD")

# Hard-code FFmpeg path for Windows stability
os.environ["PATH"] += os.pathsep + r'C:\ffmpeg\bin'

# System prompt for Llama 3 to extract live facts
EXTRACTOR_PROMPT = """
Analyze the witness testimony and extract legal facts as a JSON list.
Rules:
1. Format: [{"subject": "...", "predicate": "...", "object": "..."}]
2. Focus on names, amounts, dates, and legal sections.
3. If no clear fact is found, return an empty list [].
Only output valid JSON.
"""

# --- CORE FUNCTIONS ---

def get_truth_from_graph(subject, predicate):
    """Queries the Neo4j Truth Anchor for the stored value."""
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
    except Exception as e:
        print(f"Graph Error: {e}")
        return None

def process_and_verify(text):
    """Uses Llama 3 to convert speech to triples and checks the graph."""
    try:
        # 1. Extract Triples using local Llama 3
        response = ollama.chat(model='llama3', messages=[
            {'role': 'system', 'content': EXTRACTOR_PROMPT},
            {'role': 'user', 'content': f"Testimony: {text}"}
        ])
        
        content = response['message']['content'].strip()
        live_triples = json.loads(content)

        # 2. Compare each live fact with the Truth Anchor
        for triple in live_triples:
            subject = triple.get('subject')
            predicate = triple.get('predicate')
            live_val = triple.get('object')

            if subject and predicate:
                truth_val = get_truth_from_graph(subject, predicate)
                
                if truth_val:
                    # Logic: If the witness value differs from the graph, alert!
                    if str(live_val).lower() != str(truth_val).lower():
                        print(f"\n[!!! CONFLICT DETECTED !!!]")
                        print(f"Fact: {subject} -> {predicate}")
                        print(f"Witness Claim: {live_val}")
                        print(f"Stored Truth: {truth_val}")
                    else:
                        print(f" [Verified] {subject}'s claim matches the record.")
    except Exception as e:
        pass # Silent fail for noisy/gibberish audio

# --- MAIN LOOP (THE UNIFIED ENGINE) ---

def start_veritas_engine():
    model = whisper.load_model("small")
    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=1024)
    
    print("\n--- VERITAS-ECHO ACTIVE ---")
    print("Listening for inconsistencies...")

    try:
        while True:
            frames = []
            for _ in range(0, int(16000 / 1024 * 5)): # 5-second bursts
                frames.append(stream.read(1024))

            with wave.open("temp.wav", 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
                wf.setframerate(16000)
                wf.writeframes(b''.join(frames))

            # Transcribe and Immediately Verify
            result = model.transcribe("temp.wav", fp16=False)
            witness_text = result['text'].strip()
            
            if witness_text:
                print(f"Transcribed: {witness_text}")
                process_and_verify(witness_text)

    except KeyboardInterrupt:
        print("\nEngine Stopped.")
    finally:
        stream.close()
        p.terminate()

if __name__ == "__main__":
    start_veritas_engine()