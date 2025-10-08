"""
Quick test script to verify .env file is loaded correctly.

Usage:
    python ai_chat/test_env.py
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
env_path = Path(__file__).parent.parent / '.env'
print(f"Looking for .env file at: {env_path.absolute()}")
print(f".env file exists: {env_path.exists()}")
print()

if env_path.exists():
    load_dotenv(dotenv_path=env_path)
    print("[OK] .env file loaded successfully!")
else:
    load_dotenv()
    print("[WARNING] .env file not found in expected location, trying current directory")
print()

# Check required environment variables
print("=" * 60)
print("Environment Variables Check")
print("=" * 60)

required_vars = {
    'GOOGLE_GENAI_USE_VERTEXAI': os.getenv('GOOGLE_GENAI_USE_VERTEXAI'),
    'GOOGLE_CLOUD_PROJECT': os.getenv('GOOGLE_CLOUD_PROJECT'),
    'GOOGLE_CLOUD_LOCATION': os.getenv('GOOGLE_CLOUD_LOCATION'),
}

optional_vars = {
    'GENAI_MODEL': os.getenv('GENAI_MODEL'),
    'GENAI_TEMPERATURE': os.getenv('GENAI_TEMPERATURE'),
}

print("\nRequired Variables:")
all_set = True
for key, value in required_vars.items():
    if value:
        # Mask sensitive values
        if 'PROJECT' in key and len(value) > 10:
            display_value = f"{value[:8]}...{value[-4:]}"
        else:
            display_value = value
        print(f"  [OK] {key}: {display_value}")
    else:
        print(f"  [MISSING] {key}: NOT SET")
        all_set = False

print("\nOptional Variables:")
for key, value in optional_vars.items():
    if value:
        print(f"  [OK] {key}: {value}")
    else:
        print(f"  [INFO] {key}: Not set (will use default)")

print()
print("=" * 60)

if all_set:
    print("[SUCCESS] Configuration looks good! You can now run:")
    print("   python -m ai_chat.main")
else:
    print("[ERROR] Missing required environment variables!")
    print()
    print("Please create/update your .env file with:")
    print(f"   Location: {env_path.absolute()}")
    print()
    print("Required content:")
    print("   GOOGLE_GENAI_USE_VERTEXAI=True")
    print("   GOOGLE_CLOUD_PROJECT=YOUR_PROJECT_ID")
    print("   GOOGLE_CLOUD_LOCATION=us-central1")
    print()
    print("Example .env file:")
    print("-" * 60)
    print("GOOGLE_GENAI_USE_VERTEXAI=True")
    print("GOOGLE_CLOUD_PROJECT=1094971678787")
    print("GOOGLE_CLOUD_LOCATION=us-central1")
    print("GENAI_MODEL=gemini-2.5-flash")
    print("-" * 60)

print()

