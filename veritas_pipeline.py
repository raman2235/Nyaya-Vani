import os
import ollama
import json
import time
from neo4j import GraphDatabase

# --- CONFIGURATION FIX ---
AURA_URI = os.getenv("NEO4J_URI")
AURA_AUTH = (os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD"))

SYSTEM_PROMPT = """
You are a legal data processor. Convert text into a JSON list of triples.
Format exactly: [{"subject": "Entity", "predicate": "Relationship", "object": "Value"}]
Rules: 
1. Only output valid JSON. 
2. Be precise with names, amounts, and dates.
3. If no facts exist, return [].
"""

def extract_triples(case_id, facts):
    print(f"🔍 NLP Phase: Extracting Triples for Case {case_id}...")
    try:
        response = ollama.chat(
            model='llama3',
            messages=[
                {'role': 'system', 'content': SYSTEM_PROMPT},
                {'role': 'user', 'content': f"Extract from these legal facts: {facts}"}
            ],
            options={'temperature': 0} 
        )
        
        content = response['message']['content'].strip()
        
        # Clean JSON Markdown if present
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        
        # Robust Bracket Detection
        start_idx = content.find('[')
        end_idx = content.rfind(']') + 1
        if start_idx != -1 and end_idx != 0:
            content = content[start_idx:end_idx]

        raw_triples = json.loads(content)
        
        # Handle dictionary wrapper if LLM adds one
        if isinstance(raw_triples, dict):
            for key in ["triples", "facts", "list", "statements"]:
                if key in raw_triples:
                    raw_triples = raw_triples[key]
                    break
        
        return raw_triples if isinstance(raw_triples, list) else []
        
    except Exception as e:
        print(f"⚠️ NLP Error in Case {case_id}: {e}")
        return []

def ingest_to_neo4j(case_id, crime_type, triples):
    """Native Cypher Ingestion (No APOC required)"""
    try:
        driver = GraphDatabase.driver(AURA_URI, auth=AURA_AUTH)
        with driver.session() as session:
            # Optimized Schema: Case -> Entity -> Detail
            query = """
            MERGE (c:Case {id: $case_id})
            SET c.type = $crime
            WITH c
            UNWIND $triple_list AS t
            
            // Create/Match the Subject (e.g., Jibangshu Paul)
            MERGE (s:Entity {name: toUpper(toString(t.subject))})
            
            // Create/Match the Detail (e.g., 32.11 Lakhs)
            MERGE (d:Detail {value: toString(t.object)})
            
            // Create the Fact relationship with the predicate stored as a property
            MERGE (s)-[f:FACT]->(d)
            SET f.predicate = toLower(toString(t.predicate)),
                f.case_ref = $case_id
            
            // Link Case to the Entities involved for easy visualization
            MERGE (c)-[:INVOLVES]->(s)
            """
            session.run(query, 
                        case_id=case_id, 
                        crime=crime_type, 
                        triple_list=triples)
        driver.close()
        print(f"✅ [SUCCESS] Case {case_id} pushed to Knowledge Graph.")
    except Exception as e:
        print(f"❌ [FAILURE] Neo4j Error: {e}")

if __name__ == "__main__":
    dataset_path = 'optimal_adversarial_dataset.jsonl'
    
    if not os.path.exists(dataset_path):
        print(f"Error: {dataset_path} not found. Please place it in the same folder.")
    else:
        print("🚀 Starting Batch Ingestion (50 Cases)...")
        with open(dataset_path, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip(): continue
                case_data = json.loads(line)
                
                # Step 1: Llama 3 Extraction
                triples = extract_triples(case_data['case_id'], case_data['ground_truth_facts'])
                
                # Step 2: Neo4j Storage
                if triples:
                    ingest_to_neo4j(case_data['case_id'], case_data['crime_type'], triples)
                else:
                    print(f"⏭️ Skipping Case {case_data['case_id']} (No triples extracted)")
        
        print("\n✨ ALL DONE! Your Nyaya-Vani Truth Anchor is live.")