import ollama
import json
import time
from neo4j import GraphDatabase

# --- CONFIGURATION ---
# Use the URI and ID from your LegalBot instance
AURA_URI = "neo4j+s://611cf5d1.databases.neo4j.io" 
AURA_AUTH = ("neo4j", "wfvfnltMZNQcBJyUhjbTIa9yhXPA4GLyp44AyPbRvZs")

SYSTEM_PROMPT = """
Extract legal facts as a JSON list of triples.
Each triple MUST have: "subject", "predicate", and "object".
Example: [{"subject": "Jibangshu Paul", "predicate": "carrying_cash", "object": "32,11,000"}]
Only output the JSON. No introductory text.
"""

def extract_triples(case_id, facts):
    print(f"--- Processing Case {case_id} ---")
    for attempt in range(1, 4):
        try:
            # 1. Using the correct response structure for your Ollama version
            response = ollama.chat(
                model='llama3',
                messages=[
                    {'role': 'system', 'content': SYSTEM_PROMPT},
                    {'role': 'user', 'content': f"Extract from: {facts}"}
                ],
                options={'temperature': 0}
            )
            
            # Accessing the message content safely
            content = response['message']['content'].strip()
            
            # 2. Triple-Fence Cleaner: Removes any conversational text
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            # 3. Final Parse & Verification
            raw_triples = json.loads(content)
            
            # If AI wraps it in a dict, unwrap it
            if isinstance(raw_triples, dict) and "triples" in raw_triples:
                raw_triples = raw_triples["triples"]
            
            # Ensure it is now a list we can iterate
            if not isinstance(raw_triples, list):
                raise ValueError("Response is not a list")

            return raw_triples

        except Exception as e:
            print(f"  Attempt {attempt} failed: {e}. Retrying...")
            time.sleep(2)
    return []

def ingest_to_neo4j(case_id, crime_type, triples):
    try:
        with GraphDatabase.driver(AURA_URI, auth=AURA_AUTH) as driver:
            with driver.session() as session:
                for t in triples:
                    # Defensive programming: ensure t is a dict before calling .get()
                    if not isinstance(t, dict): continue
                    
                    session.run("""
                        MERGE (c:Case {id: $case_id})
                        SET c.type = $crime
                        MERGE (s:Entity {name: $sub})
                        MERGE (o:Detail {value: $obj})
                        MERGE (s)-[:FACT {type: $pred}]->(o)
                        MERGE (c)-[:INVOLVES]->(s)
                    """, case_id=case_id, crime=crime_type, 
                         sub=t.get('subject', 'Unknown'), 
                         pred=t.get('predicate', 'Unknown'), 
                         obj=t.get('object', 'N/A'))
        print(f"  [SUCCESS] Case {case_id} pushed to Aura.")
    except Exception as e:
        print(f"  [FAILURE] Neo4j Error: {e}")

if __name__ == "__main__":
    # Accesses your 50-case dataset
    with open('optimal_adversarial_dataset.jsonl', 'r') as f:
        for line in f:
            if not line.strip(): continue
            case = json.loads(line)
            data_triples = extract_triples(case['case_id'], case['ground_truth_facts'])
            if data_triples:
                ingest_to_neo4j(case['case_id'], case['crime_type'], data_triples)