"""
Convenient script to run AI Chat service.
This script can be run from any directory.
"""
import sys
from pathlib import Path

# Add parent directory to path
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

# Import uvicorn
import uvicorn

if __name__ == "__main__":
    print("="*60)
    print("🚀 Starting AI Chat Service...")
    print("="*60)
    print("📝 API Documentation: http://localhost:8000/docs")
    print("🏥 Health Check: http://localhost:8000/api/v1/chat/health")
    print("="*60)
    print()
    
    # Use import string to enable reload
    uvicorn.run(
        "ai_chat.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

