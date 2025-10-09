"""
Simple audio recording utility for creating test WAV files.

This script records audio from your microphone and saves it as a WAV file
in the correct format for Google Cloud Speech-to-Text (LINEAR16, 16kHz, mono).
"""
import pyaudio
import wave
import sys
from pathlib import Path


def record_audio(
    output_file: str = "recorded_audio.wav",
    duration_seconds: int = 5,
    sample_rate: int = 16000,
    channels: int = 1,
    chunk_size: int = 1024
):
    """
    Record audio from microphone and save to WAV file.
    
    Args:
        output_file: Output WAV file path
        duration_seconds: Recording duration in seconds
        sample_rate: Sample rate in Hz (default: 16000)
        channels: Number of channels (1=mono, 2=stereo, default: 1)
        chunk_size: Audio chunk size in frames
    """
    audio_format = pyaudio.paInt16  # 16-bit LINEAR16
    
    # Initialize PyAudio
    audio = pyaudio.PyAudio()
    
    print("\n" + "=" * 60)
    print(f"Recording Audio")
    print("=" * 60)
    print(f"Output File: {output_file}")
    print(f"Duration: {duration_seconds} seconds")
    print(f"Sample Rate: {sample_rate} Hz")
    print(f"Channels: {channels} ({'mono' if channels == 1 else 'stereo'})")
    print(f"Format: LINEAR16 (16-bit PCM)")
    print("=" * 60)
    
    try:
        # Open microphone stream
        stream = audio.open(
            format=audio_format,
            channels=channels,
            rate=sample_rate,
            input=True,
            frames_per_buffer=chunk_size
        )
        
        print("\nRecording started... Speak into the microphone!")
        print(f"Recording for {duration_seconds} seconds...")
        
        frames = []
        
        # Calculate number of chunks to record
        num_chunks = int(sample_rate / chunk_size * duration_seconds)
        
        # Record audio
        for i in range(num_chunks):
            data = stream.read(chunk_size)
            frames.append(data)
            
            # Show progress
            progress = (i + 1) / num_chunks * 100
            print(f"Progress: {progress:.1f}%", end='\r')
        
        print("\nRecording completed!")
        
        # Stop and close stream
        stream.stop_stream()
        stream.close()
        
        # Save to WAV file
        print(f"\nSaving to {output_file}...")
        with wave.open(output_file, 'wb') as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(audio.get_sample_size(audio_format))
            wf.setframerate(sample_rate)
            wf.writeframes(b''.join(frames))
        
        # Get file size
        file_size = Path(output_file).stat().st_size
        file_size_kb = file_size / 1024
        
        print(f"✓ Audio saved successfully!")
        print(f"  File: {output_file}")
        print(f"  Size: {file_size_kb:.1f} KB")
        print(f"\nYou can now use this file with the Speech-to-Text API:")
        print(f"  python ai_chat/examples/speech_client_example.py {output_file}")
        
    except Exception as e:
        print(f"\nError: {str(e)}")
        return False
        
    finally:
        audio.terminate()
    
    return True


def main():
    """Main function."""
    print("\nAudio Recording Utility for Speech-to-Text")
    print("=" * 60)
    
    # Get parameters from command line or use defaults
    output_file = sys.argv[1] if len(sys.argv) > 1 else "recorded_audio.wav"
    duration = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    
    # Record audio
    success = record_audio(
        output_file=output_file,
        duration_seconds=duration
    )
    
    if success:
        print("\n✓ Recording completed successfully!")
    else:
        print("\n✗ Recording failed!")
        sys.exit(1)


if __name__ == "__main__":
    print("\nUsage:")
    print(f"  python {sys.argv[0]} [output_file.wav] [duration_seconds]")
    print("\nExamples:")
    print(f"  python {sys.argv[0]}                        # Record 5 seconds to 'recorded_audio.wav'")
    print(f"  python {sys.argv[0]} test.wav               # Record 5 seconds to 'test.wav'")
    print(f"  python {sys.argv[0]} test.wav 10            # Record 10 seconds to 'test.wav'")
    print()
    
    main()

