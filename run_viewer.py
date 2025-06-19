#!/usr/bin/env python3
"""
Launcher script for SAT Question Viewer
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from sat_question_viewer import main
    print("🚀 Starting SAT Question Viewer...")
    main()
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure sat_question_viewer.py is in the same directory")
except Exception as e:
    print(f"❌ Error running application: {e}")
    input("Press Enter to exit...") 