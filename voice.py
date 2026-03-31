import pyttsx3

def test_voice():
    try:
        engine = pyttsx3.init()
        # You can list voices to find a better 'legal' sounding one
        voices = engine.getProperty('voices')
        # On Windows, voices[0] is usually 'David' (Male) and voices[1] is 'Zira' (Female)
        engine.setProperty('voice', voices[0].id) 
        engine.setProperty('rate', 150)
        
        print("Testing Nyaya-Vani Voice Output...")
        engine.say("Voice engine initialized. Ready to detect inconsistencies.")
        engine.runAndWait()
        print("Test Successful!")
    except Exception as e:
        print(f"Voice Error: {e}. Try running 'pip install pywin32' if on Windows.")

if __name__ == "__main__":
    test_voice()