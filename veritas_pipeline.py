import os
import ollama
import json
import time
from neo4j import GraphDatabase

# --- CONFIGURATION ---
AURA_URI = "neo4j+s://611cf5d1.databases.neo4j.io" 
AURA_AUTH = ("neo4j", "wfvfnltMZNQcBJyUhjbTIa9yhXPA4GLyp44AyPbRvZs")

SYSTEM_PROMPT = """
You are a legal data processor. Convert text into a JSON list of triples.
Format: {"subject": "Entity Name", "predicate": "Relationship", "object": "Value"}
Rules: 
1. Only output JSON. 
2. Be precise with names and amounts.
3. If no facts exist, return [].
"""

def extract_triples(case_id, facts):
    print(f"--- Processing Case {case_id} ---")
    for attempt in range(1, 3):
        try:
            response = ollama.chat(
                model='llama3',
                messages=[
                    {'role': 'system', 'content': SYSTEM_PROMPT},
                    {'role': 'user', 'content': f"Extract from: {facts}"}
                ],
                options={'temperature': 0} 
            )
            
            content = response['message']['content'].strip()
            
            # Robust JSON Cleaning
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            # Anchor detection for JSON arrays
            start_idx = content.find('[')
            end_idx = content.rfind(']') + 1
            if start_idx != -1 and end_idx != 0:
                content = content[start_idx:end_idx]

            raw_triples = json.loads(content)
            
            # Ensure it's a flat list
            if isinstance(raw_triples, dict):
                for key in ["triples", "facts", "data"]:
                    if key in raw_triples:
                        raw_triples = raw_triples[key]
                        break
            
            return raw_triples if isinstance(raw_triples, list) else []
            
        except Exception as e:
            print(f"  Attempt {attempt} failed (JSON Error). Retrying...")
            time.sleep(1)
    return []

def ingest_to_neo4j(case_id, crime_type, triples):
    """Batched ingestion with Case-Insensitive Deduplication."""
    try:
        with GraphDatabase.driver(AURA_URI, auth=AURA_AUTH) as driver:
            with driver.session() as session:
                # Cypher query with 'ON CREATE SET' to avoid duplicate relationships
                query = """
                MERGE (c:Case {id: $case_id})
                SET c.type = $crime
                WITH c
                UNWIND $triple_list AS t
                // Create Subject (Normalized)
                MERGE (s:Entity {name: apoc.text.capitalizeAll(toString(t.subject))})
                // Create Object (Normalized)
                MERGE (o:Detail {value: toString(t.object)})
                // Create Relationship with Predicate
                MERGE (s)-[f:FACT]->(o)
                SET f.type = toLower(toString(t.predicate))
                // Connect Case to Entity
                MERGE (c)-[:INVOLVES]->(s)
                """
                session.run(query, 
                            case_id=case_id, 
                            crime=crime_type, 
                            triple_list=triples)
                
        print(f"  [SUCCESS] Knowledge Graph updated for Case {case_id}.")
    except Exception as e:
        print(f"  [FAILURE] Neo4j Ingestion Error: {e}")

if __name__ == "__main__":
    dataset_path = 'optimal_adversarial_dataset.jsonl'
    
    if not os.path.exists(dataset_path):
        print(f"Error: {dataset_path} not found in current directory.")
    else:
        with open(dataset_path, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip(): continue
                case_data = json.loads(line)
                
                # 1. NLP Phase (Llama 3)
                extracted = extract_triples(case_data['case_id'], case_data['ground_truth_facts'])
                
                # 2. Graph Phase (Neo4j)
                if extracted:
                    ingest_to_neo4j(case_data['case_id'], case_data['crime_type'], extracted)
                else:
                    print(f"  [SKIP] Case {case_data['case_id']} - No facts found.")