"""
Example client for testing Speech-to-Text API endpoints.

This script demonstrates how to:
1. Transcribe an audio file
2. Stream transcription from microphone
3. Stream transcription from uploaded audio file
"""
import requests
import json
import sys
from pathlib import Path

# API base URL
BASE_URL = "http://localhost:8000/api/v1/speech"


def transcribe_audio_file(file_path: str, language_code: str = "en-US"):
    """
    Transcribe an audio file using the /transcribe endpoint.
    
    Args:
        file_path: Path to audio file
        language_code: Language code for recognition
    """
    print(f"\n=== Transcribing Audio File: {file_path} ===")
    
    url = f"{BASE_URL}/transcribe"
    
    with open(file_path, 'rb') as f:
        files = {'file': f}
        params = {'language_code': language_code}
        
        response = requests.post(url, files=files, params=params)
    
    if response.status_code == 200:
        result = response.json()
        print(f"\nTranscript: {result['transcript']}")
        print(f"Confidence: {result.get('confidence', 'N/A')}")
        print(f"Language: {result['language_code']}")
    else:
        print(f"Error: {response.status_code} - {response.text}")


def stream_microphone_transcription(
    duration_seconds: int = 10,
    language_code: str = "en-US",
    single_utterance: bool = False
):
    """
    Stream transcription from microphone.
    
    Args:
        duration_seconds: Maximum recording duration
        language_code: Language code for recognition
        single_utterance: Stop after single utterance
    """
    print(f"\n=== Streaming Microphone Transcription ===")
    print(f"Duration: {duration_seconds}s, Language: {language_code}")
    print("Speak into the microphone...\n")
    
    url = f"{BASE_URL}/stream/microphone"
    
    payload = {
        "duration_seconds": duration_seconds,
        "language_code": language_code,
        "single_utterance": single_utterance
    }
    
    response = requests.post(url, json=payload, stream=True)
    
    if response.status_code == 200:
        print("Receiving transcription results:\n")
        print("-" * 80)
        
        for line in response.iter_lines():
            if line:
                result = json.loads(line.decode('utf-8'))
                
                if 'error' in result:
                    print(f"\nError: {result['error']}")
                    break
                
                is_final = result.get('is_final', False)
                transcript = result.get('transcript', '')
                confidence = result.get('confidence')
                stability = result.get('stability')
                
                status = "FINAL" if is_final else "interim"
                
                if is_final:
                    print(f"\n[{status}] {transcript}")
                    print(f"         Confidence: {confidence:.2f}")
                else:
                    print(f"[{status}] {transcript}", end='\r')
        
        print("\n" + "-" * 80)
    else:
        print(f"Error: {response.status_code} - {response.text}")


def stream_audio_file_transcription(
    file_path: str,
    language_code: str = "en-US",
    single_utterance: bool = False
):
    """
    Stream transcription of an uploaded audio file.
    
    Args:
        file_path: Path to audio file
        language_code: Language code for recognition
        single_utterance: Stop after single utterance
    """
    print(f"\n=== Streaming Audio File Transcription: {file_path} ===")
    
    url = f"{BASE_URL}/stream/upload"
    
    with open(file_path, 'rb') as f:
        files = {'file': f}
        params = {
            'language_code': language_code,
            'single_utterance': single_utterance
        }
        
        response = requests.post(url, files=files, params=params, stream=True)
    
    if response.status_code == 200:
        print("Receiving transcription results:\n")
        print("-" * 80)
        
        for line in response.iter_lines():
            if line:
                result = json.loads(line.decode('utf-8'))
                
                if 'error' in result:
                    print(f"\nError: {result['error']}")
                    break
                
                is_final = result.get('is_final', False)
                transcript = result.get('transcript', '')
                confidence = result.get('confidence')
                
                status = "FINAL" if is_final else "interim"
                
                if is_final:
                    print(f"\n[{status}] {transcript}")
                    if confidence:
                        print(f"         Confidence: {confidence:.2f}")
                else:
                    print(f"[{status}] {transcript}", end='\r')
        
        print("\n" + "-" * 80)
    else:
        print(f"Error: {response.status_code} - {response.text}")


def check_health():
    """Check Speech-to-Text service health."""
    print(f"\n=== Checking Service Health ===")
    
    url = f"{BASE_URL}/health"
    response = requests.get(url)
    
    if response.status_code == 200:
        result = response.json()
        print(f"Status: {result['status']}")
        print(f"Service: {result['service']}")
        print(f"Model: {result['model']}")
    else:
        print(f"Error: {response.status_code} - {response.text}")


def main():
    """Main function with example usage."""
    print("Speech-to-Text API Client Examples")
    print("=" * 80)
    
    # Check service health
    check_health()
    
    # Example 1: Stream microphone transcription
    # Note: This requires a microphone on the SERVER side
    print("\n" + "=" * 80)
    print("Example 1: Stream Microphone Transcription")
    print("=" * 80)
    print("\nThis will capture audio from the SERVER's microphone.")
    response = input("Do you want to try this? (y/n): ")
    
    if response.lower() == 'y':
        stream_microphone_transcription(
            duration_seconds=10,
            language_code="en-US",
            single_utterance=False
        )
    
    # Example 2: Transcribe audio file (if provided)
    print("\n" + "=" * 80)
    print("Example 2: Transcribe Audio File")
    print("=" * 80)
    
    if len(sys.argv) > 1:
        audio_file = sys.argv[1]
        if Path(audio_file).exists():
            # Simple transcription
            transcribe_audio_file(audio_file)
            
            # Streaming transcription
            print("\n" + "=" * 80)
            print("Example 3: Stream Audio File Transcription")
            print("=" * 80)
            stream_audio_file_transcription(audio_file)
        else:
            print(f"Audio file not found: {audio_file}")
    else:
        print("\nTo test audio file transcription, run:")
        print(f"  python {sys.argv[0]} <path_to_audio_file.wav>")
        print("\nNote: Audio file should be LINEAR16, 16kHz WAV format")


if __name__ == "__main__":
    main()

