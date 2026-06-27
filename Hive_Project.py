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

# RAZINE_DIR = os.path.dirname(os.path.abspath(__file__))
# if RAZINE_DIR not in sys.path:
#     sys.path.insert(0, RAZINE_DIR)
#     sys.path.insert(1, os.path.join(RAZINE_DIR, "src"))

# from src.agents.agent_base import AIAgent
# from src.core.workplace import generate_team_from_director
# from src.core.file_manager import get_template_prompt # <-- New import

# if __name__ == "__main__":
#     print("--- Starting Phase 3: Template-based Initialization ---")
    
#     # 1. Dynamic prompt loading from the text file
#     director_prompt = get_template_prompt("director_prompt.txt")
    
#     # Error checking
#     if "Error" in director_prompt: 
#         print(director_prompt)
#         sys.exit(1)
    
#     project_name = "Project_Alpha"
    
#     # 2. Agent creation with its actual brain (the template)
#     director = AIAgent(
#         name=f"{project_name}_Director", 
#         role="Director", 
#         role_category="director",
#         project_name=project_name,
#         system_prompt=director_prompt, 
#         model_name="Qwen3.6_27B_Q3:latest"
#     )
    
#     boss_brief = "Develop a text-based investigation game in Python with a simple GUI."
#     print(f"[President]: {boss_brief}")
    
#     generate_team_from_director(director, boss_brief)