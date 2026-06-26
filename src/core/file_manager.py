
import os
import json

def setup_agent_directory(project_name: str, role_category: str, agent_name: str, system_prompt: str):
    """Crée les dossiers et fichiers de base pour un agent spécifique"""
    base_path = f"data/{project_name}/agents_storage/{role_category}/{agent_name}"
    os.makedirs(base_path, exist_ok=True)

    # Création du fichier de prompt système
    with open(f"{base_path}/system_prompt.txt", "w", encoding="utf-8") as f:
        f.write(system_prompt)

    # Initialisation de la mémoire si inexistante
    if not os.path.exists(f"{base_path}/memory.json"):
        save_json(f"{base_path}/memory.json", [])

    # Initialisation des stats si inexistantes
    if not os.path.exists(f"{base_path}/stats.json"):
        initial_stats = {
            "tasks_started": 0,
            "tasks_validated": 0,
            "tasks_failed": 0,
            "tokens_produced": 0,
            "total_work_time_sec": 0.0,
            "average_time_per_task_sec": 0.0
        }
        save_json(f"{base_path}/stats.json", initial_stats)

    return base_path

def save_json(filepath: str, data):
    """Utilitaire pour sauvegarder proprement un fichier JSON"""
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def load_json(filepath: str, default_value):
    """Utilitaire pour charger un fichier JSON de manière sécurisée"""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default_value

def get_template_prompt(role_filename: str) -> str:
    """
    Charge un prompt système depuis le dossier src/agents/templates.
    Exemple: get_template_prompt('director_prompt.txt')
    """
    # Remonte de src/core vers src/agents/templates de façon robuste
    current_dir = os.path.dirname(os.path.abspath(__file__))
    template_path = os.path.join(current_dir, "..", "agents", "templates", role_filename)
    
    try:
        with open(template_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return f"Erreur : Le fichier template '{role_filename}' est introuvable au chemin {template_path}"


def update_project_state(project_name: str, state_update: dict):
    """Updates the global state.json at the root of the project."""
    project_dir = os.path.join("data", project_name)
    state_file = os.path.join(project_dir, "state.json")
    
    current_state = load_json(state_file, {"status": "Initialized", "progress": []})
    current_state.update(state_update)
    save_json(state_file, current_state)

def read_file_content(filepath: str) -> str:
    """Reads a text file."""
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    return ""