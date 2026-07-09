import os
import azure.cognitiveservices.speech as speechsdk
from dotenv import load_dotenv

load_dotenv()
SPEECH_KEY = os.getenv("AZURE_SPEECH_KEY")
SPEECH_REGION = os.getenv("AZURE_SPEECH_REGION")

def initialize_speech_config(lang_choice="hi"):
    """Sets up the Azure configuration dynamically based on language choice."""
    speech_config = speechsdk.SpeechConfig(subscription=SPEECH_KEY, region=SPEECH_REGION)
    
    if lang_choice.lower() == "en":
        speech_config.speech_recognition_language = "en-IN"
        speech_config.speech_synthesis_voice_name = "en-IN-NeerjaNeural"
    else:
        speech_config.speech_recognition_language = "hi-IN"
        speech_config.speech_synthesis_voice_name = "hi-IN-SwaraNeural"
        
    return speech_config

def listen_and_transcribe(lang_choice="hi"):
    """
    DAY 8 INTEGRATION FUNCTION 1:
    Listens to the microphone and returns the transcribed text string.
    Hitesh will pass this string to his RAG pipeline.
    """
    try:
        config = initialize_speech_config(lang_choice)
        audio_config = speechsdk.audio.AudioConfig(use_default_microphone=True)
        recognizer = speechsdk.SpeechRecognizer(speech_config=config, audio_config=audio_config)
        
        print(f"[Voice Module] Listening in {config.speech_recognition_language}...")
        result = recognizer.recognize_once_async().get()
        
        if result.reason == speechsdk.ResultReason.RecognizedSpeech:
            return result.text
        else:
            print("[Voice Module Error] Audio not recognized or mic silent.")
            return None
    except Exception as e:
        print(f"[Voice Module Error] STT Failed: {e}")
        return None

def speak_text(text_to_speak, lang_choice="hi"):
    """
    DAY 8 INTEGRATION FUNCTION 2:
    Takes any text string (like Hitesh's AI answers) and reads it out loud.
    """
    if not text_to_speak:
        return
        
    try:
        config = initialize_speech_config(lang_choice)
        synthesizer = speechsdk.SpeechSynthesizer(speech_config=config)
        print(f"[Voice Module] Speaking: '{text_to_speak}'")
        synthesizer.speak_text_async(text_to_speak).get()
    except Exception as e:
        print(f"[Voice Module Error] TTS Failed: {e}")