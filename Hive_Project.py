import os
import sys
import subprocess

# 1. Configuration des chemins
RAZINE_DIR = os.path.dirname(os.path.abspath(__file__))
if RAZINE_DIR not in sys.path:
    sys.path.insert(0, RAZINE_DIR)
    sys.path.insert(1, os.path.join(RAZINE_DIR, "src"))

if __name__ == "__main__":
    print("--- [Hive Project] Launcher ---")
    
    # 2. Cible du script UI
    ui_script = os.path.join(RAZINE_DIR, "src", "ui", "app.py")
    
    if not os.path.exists(ui_script):
        print(f"Error: UI script not found at {ui_script}")
        sys.exit(1)
        
    print("[Launcher] Starting Streamlit interface...")
    
    # 3. Lancement du processus unique
    try:
        subprocess.run([sys.executable, "-m", "streamlit", "run", ui_script], check=True)
    except KeyboardInterrupt:
        print("\n--- Hive Project Closed Interactively ---")
    except Exception as e:
        print(f"Launcher Error: {str(e)}")