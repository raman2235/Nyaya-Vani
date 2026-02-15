import json
import ollama
import time
from collections import defaultdict

# 1. STRATIFIED SELECTION LOGIC
def select_optimal_cases(filename, cases_per_category=10):
    with open(filename, 'r') as f:
        all_cases = json.load(f)
    
    # Categorize by crime type
    categorized = defaultdict(list)
    for case in all_cases:
        categorized[case.get('crime_type', 'Others')].append(case)
    
    selected_cases = []
    # Target diverse categories for maximum accuracy
    targets = ['Narcotics', 'Murder', 'Sexual Offense', 'Fraud or Cheating', 'Kidnapping']
    
    for category in targets:
        pool = categorized[category]
        # Prioritize Landmark Cases to prevent underfitting
        landmarks = [c for c in pool if c.get('landmark_case') == True]
        regulars = [c for c in pool if c.get('landmark_case') != True]
        
        # Balance the selection
        selection = landmarks + regulars
        selected_cases.extend(selection[:cases_per_category])
    
    return selected_cases

# 2. ADVERSARIAL SYNTHESIS ENGINE
def generate_optimal_lie(case_data):
    facts = case_data.get('facts', 'No facts available.')
    id = case_data.get('case_id', 'Unknown')
    
    prompt = f"""
    Act as a legal witness in a deposition. 
    CASE FACTS: {facts}
    
    TASK: Write a 6-turn dialogue between a PROSECUTOR and WITNESS.
    The witness must subtly LIE about a core factual detail.
    
    FORMAT:
    PROSECUTOR: [Question]
    WITNESS: [Subtle Lie]
    """
    
    try:
        response = ollama.chat(model='llama3', messages=[
            {'role': 'system', 'content': 'You are a high-accuracy legal data generator.'},
            {'role': 'user', 'content': prompt}
        ])
        return response['message']['content']
    except Exception as e:
        print(f"Error on case {id}: {e}")
        return None

# 3. MAIN EXECUTION PIPELINE
if __name__ == "__main__":
    print("Selecting optimal stratified dataset...")
    optimal_set = select_optimal_cases('indian_bail_judgments.json')
    
    print(f"Dataset Ready. Generating adversarial transcripts for {len(optimal_set)} cases...")
    
    with open("optimal_adversarial_dataset.jsonl", "w") as out:
        for case in optimal_set:
            print(f"Synthesizing Case ID: {case['case_id']} ({case['crime_type']})...")
            transcript = generate_optimal_lie(case)
            
            if transcript:
                record = {
                    "case_id": case['case_id'],
                    "crime_type": case['crime_type'],
                    "ground_truth_facts": case['facts'],
                    "adversarial_transcript": transcript,
                    "label": "CONFLICT_DETECTED"
                }
                out.write(json.dumps(record) + "\n")
            time.sleep(0.5) # Protect local hardware

    print("Success! Final optimal dataset saved to 'optimal_adversarial_dataset.jsonl'.")