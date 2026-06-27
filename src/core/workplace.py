import os
import json
from src.agents.agent_base import AIAgent
from src.core.file_manager import setup_agent_directory, get_template_prompt, load_json, save_json
from src.core.json_validator import validate_team_structure

def format_name(text: str) -> str:
    """Cleans a string to make it a clean identifier (without spaces)"""
    return text.strip().replace(" ", "_").replace("-", "_")

def log_state_milestone(project_name: str, status: str, phase: str, detail: str):
    """Met à jour le statut global et ajoute une ligne d'historique dans state.json"""
    project_dir = os.path.join("data", project_name)
    state_file = os.path.join(project_dir, "state.json")
    
    current_state = load_json(state_file, {"status": "Initialized", "current_phase": "", "history": []})
    current_state["status"] = status
    current_state["current_phase"] = phase
    
    if "history" not in current_state:
        current_state["history"] = []
        
    current_state["history"].append({
        "phase": phase,
        "detail": detail
    })
    save_json(state_file, current_state)

def generate_team_from_director(director: AIAgent, project_brief: str):
    print(f"\n[Workplace] : Sending project brief to Director {director.name}...")
    
    instruction_prompt = (
        f"Analyze this project brief: '{project_brief}'.\n"
        "Generate the required team structure.\n"
        "Respond ONLY with a JSON matching this exact structure. "
        "Use short, unique words for 'team_name' and 'task_name' (e.g., 'Backend', 'UI', 'Database'):\n"
        "{\n"
        "  \"managers\": [\n"
        "    {\n"
        "      \"team_name\": \"ShortTeamName\",\n"
        "      \"role\": \"Detailed description of their role\",\n"
        "      \"employees\": [\n"
        "        {\"task_name\": \"ShortTaskName\", \"role\": \"Their specific role\"}\n"
        "      ]\n"
        "    }\n"
        "  ]\n"
        "}"
    )
    
    message_to_send = instruction_prompt
    attempts = 0
    max_retries = 3
    team_structure = None

    while attempts < max_retries:
        attempts += 1
        if attempts > 1:
            print(f"[Workplace] : Correction attempt {attempts}/{max_retries}...")

        raw_json_response = director.ask(message_to_send)
        is_valid, parsed_data, error_message = validate_team_structure(raw_json_response)
        
        if is_valid:
            print("[Workplace] : 100% valid JSON! Production approved.")
            team_structure = parsed_data
            director.log_validation(success=True)
            break
        else:
            print(f"[Workplace Error] Failure: {error_message}")
            director.log_validation(success=False)
            if attempts < max_retries:
                message_to_send = f"Error: {error_message}\nCorrect your full JSON format."
            else:
                return False, {}

    print("[Workplace] : Team creation with strict nomenclature...")
    project = format_name(director.project_name)
    
    # Chargement des pré-prompts pour l'initialisation des répertoires
    manager_template = get_template_prompt("manager_preprompt.txt")
    employee_template = get_template_prompt("employee_preprompt.txt")
    
    try:
        for manager in team_structure.get("managers", []):
            team = format_name(manager['team_name'])
            manager_name = f"{project}_{team}_Manager"
            
            # Assemblage complet du prompt système initial du manager
            full_manager_prompt = f"{manager_template}\n\nYour Team Role:\n{manager['role']}"
            setup_agent_directory(director.project_name, "managers", manager_name, full_manager_prompt)
            print(f" -> Created: {manager_name}")
            
            # Mise à jour de l'état par le Manager lors de la planification de ses employés
            log_state_milestone(
                director.project_name, "In Progress", f"Manager {team} Initialization", 
                f"Manager {manager_name} defined the sub-tasks for their team."
            )
            
            for employee in manager.get("employees", []):
                task = format_name(employee['task_name'])
                employee_name = f"{project}_{team}_{task}_Employee"
                
                # Assemblage complet du prompt système initial de l'employé
                full_employee_prompt = f"{employee_template}\n\nYour Task Role:\n{employee['role']}"
                setup_agent_directory(director.project_name, "employees", employee_name, full_employee_prompt)
                print(f"    -> Created: {employee_name}")
                
        print("\n[Workplace] : Nomenclature applied successfully in /data!")
        return True, team_structure
    except Exception as e:
        print(f"[Workplace Error] : {str(e)}")
        return False, {}


def execute_project_workflow(director: AIAgent, team_structure: dict, project_brief: str):
    """Exécute la production de A à Z (Séquentiel strict)"""
    
    log_state_milestone(director.project_name, "In Progress", "Team Assembly Completed", "All structures and agents are initialized.")
    project_name_clean = format_name(director.project_name)
    all_managers_artifacts = []

    manager_template = get_template_prompt("manager_preprompt.txt")
    employee_template = get_template_prompt("employee_preprompt.txt")

    # Boucle sur les Managers
    for manager_data in team_structure.get("managers", []):
        team_name = format_name(manager_data['team_name'])
        manager_name = f"{project_name_clean}_{team_name}_Manager"
        
        log_state_milestone(director.project_name, "In Progress", f"Manager {team_name} Activation", f"Manager {manager_name} is starting supervising duties.")
        
        manager_system_prompt = f"{manager_template}\n\nYour Team Role:\n{manager_data['role']}"
        manager_agent = AIAgent(
            name=manager_name, role=manager_data['role'], role_category="managers",
            project_name=director.project_name, system_prompt=manager_system_prompt, 
            model_name=director.model_name
        )
        
        team_artifacts = []
        
        # Boucle sur les Employés
        for emp_data in manager_data.get("employees", []):
            task_name = format_name(emp_data['task_name'])
            emp_name = f"{project_name_clean}_{team_name}_{task_name}_Employee"
            
            log_state_milestone(director.project_name, "In Progress", f"Employee {task_name} Working", f"Employee {emp_name} is processing assigned sub-task.")
            
            employee_system_prompt = f"{employee_template}\n\nYour Task Role:\n{emp_data['role']}"
            employee_agent = AIAgent(
                name=emp_name, role=emp_data['role'], role_category="employees",
                project_name=director.project_name, system_prompt=employee_system_prompt, 
                model_name=director.model_name
            )
            
            emp_instruction = f"Based on the project brief: '{project_brief}', execute your role: {emp_data['role']}."
            emp_result = employee_agent.ask(emp_instruction)
            
            # Sauvegarde Employé utilisant le préfixe artifact_ et son nom propre
            artifact_filename = f"artifact_{emp_name}.md"
            employee_agent.save_artifact(artifact_filename, emp_result)
            team_artifacts.append(f"--- Task: {task_name} (by {emp_name}) ---\n{emp_result}\n")
            
            log_state_milestone(director.project_name, "In Progress", f"Employee {task_name} Done", f"Employee {emp_name} finalized production and saved {artifact_filename}.")
            
        # Action Manager (Agrégation & Validation)
        log_state_milestone(director.project_name, "In Progress", f"Manager {team_name} Validation", f"Manager {manager_name} is aggregating and validating team productions.")
        
        mgr_instruction = "Synthesize and finalize the following outputs from your team into a cohesive module:\n" + "\n".join(team_artifacts)
        mgr_result = manager_agent.ask(mgr_instruction)
        
        # Sauvegarde Manager utilisant le préfixe artifact_ et son nom propre
        mgr_artifact_filename = f"artifact_{manager_name}_final.md"
        manager_agent.save_artifact(mgr_artifact_filename, mgr_result)
        all_managers_artifacts.append(f"--- Team: {team_name} Module ---\n{mgr_result}\n")
        
        log_state_milestone(director.project_name, "In Progress", f"Manager {team_name} Done", f"Manager {manager_name} completed module integration into {mgr_artifact_filename}.")

    # Action Directeur (Agrégation finale)
    log_state_milestone(director.project_name, "In Progress", "Director Final Integration", f"Director {director.name} is building the final solution package.")
    
    dir_instruction = "Combine all manager modules into the final project deliverable:\n" + "\n".join(all_managers_artifacts)
    final_project_result = director.ask(dir_instruction)
    
    # Sauvegarde Finale Directeur
    director.save_artifact("artifact_FINAL_PROJECT_OUTPUT.md", final_project_result)
    log_state_milestone(director.project_name, "Completed", "Project Delivery", "Director integrated all modules. Deliverable saved as artifact_FINAL_PROJECT_OUTPUT.md.")
    
    return True