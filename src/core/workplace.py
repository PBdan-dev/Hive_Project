import os
from src.agents.agent_base import AIAgent
from src.core.file_manager import setup_agent_directory, update_project_state, read_file_content
from src.core.json_validator import validate_team_structure

def format_name(text: str) -> str:
    """Cleans a string to make it a clean identifier (without spaces)"""
    return text.strip().replace(" ", "_").replace("-", "_")

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
    
    try:
        for manager in team_structure.get("managers", []):
            team = format_name(manager['team_name'])
            manager_name = f"{project}_{team}_Manager"
            
            setup_agent_directory(director.project_name, "managers", manager_name, manager['role'])
            print(f" -> Created: {manager_name}")
            
            for employee in manager.get("employees", []):
                task = format_name(employee['task_name'])
                employee_name = f"{project}_{team}_{task}_Employee"
                
                setup_agent_directory(director.project_name, "employees", employee_name, employee['role'])
                print(f"    -> Created: {employee_name}")
                
        print("\n[Workplace] : Nomenclature applied successfully in /data!")
        return True, team_structure
    except Exception as e:
        print(f"[Workplace Error] : {str(e)}")
        return False, {}


def execute_project_workflow(director: AIAgent, team_structure: dict, project_brief: str):
    """Exécute la production de A à Z (Séquentiel strict)"""
    
    # Étape 1 : Le Directeur initialise l'état
    update_project_state(director.project_name, {"status": "In Progress", "current_phase": "Team Assembly"})
    project_name_clean = format_name(director.project_name)
    all_managers_artifacts = []

    # Étape 2 : Boucle sur les Managers
    for manager_data in team_structure.get("managers", []):
        team_name = format_name(manager_data['team_name'])
        manager_name = f"{project_name_clean}_{team_name}_Manager"
        
        update_project_state(director.project_name, {"current_phase": f"Manager {team_name} Working"})
        
        # Instanciation du Manager
        manager_agent = AIAgent(
            name=manager_name, role=manager_data['role'], role_category="managers",
            project_name=director.project_name, system_prompt=f"You are the Manager of {team_name}. Aggregate employee work.", 
            model_name=director.model_name
        )
        
        team_artifacts = []
        
        # Étape 3 : Boucle sur les Employés du Manager
        for emp_data in manager_data.get("employees", []):
            task_name = format_name(emp_data['task_name'])
            emp_name = f"{project_name_clean}_{team_name}_{task_name}_Employee"
            
            # Instanciation de l'Employé
            employee_agent = AIAgent(
                name=emp_name, role=emp_data['role'], role_category="employees",
                project_name=director.project_name, system_prompt=f"You are {task_name}. Execute your task strictly.", 
                model_name=director.model_name
            )
            
            # Action Employé : Production
            emp_instruction = f"Based on the project brief: '{project_brief}', execute your role: {emp_data['role']}."
            emp_result = employee_agent.ask(emp_instruction)
            
            # 1. SAUVEGARDE EMPLOYÉ
            artifact_path = employee_agent.save_artifact("production.md", emp_result)
            team_artifacts.append(f"--- Task: {task_name} ---\n{emp_result}\n")
            
        # Étape 4 : Action Manager (Agrégation)
        mgr_instruction = "Synthesize and finalize the following outputs from your team into a cohesive module:\n" + "\n".join(team_artifacts)
        mgr_result = manager_agent.ask(mgr_instruction)
        
        # 2. SAUVEGARDE MANAGER
        mgr_artifact_path = manager_agent.save_artifact(f"{team_name}_final.md", mgr_result)
        all_managers_artifacts.append(f"--- Team: {team_name} ---\n{mgr_result}\n")

    # Étape 5 : Action Directeur (Agrégation finale)
    update_project_state(director.project_name, {"current_phase": "Director Final Aggregation"})
    
    dir_instruction = "Combine all manager modules into the final project deliverable:\n" + "\n".join(all_managers_artifacts)
    final_project_result = director.ask(dir_instruction)
    
    # 3. SAUVEGARDE DIRECTEUR & MISE A JOUR ETAT
    director.save_artifact("FINAL_PROJECT_OUTPUT.md", final_project_result)
    update_project_state(director.project_name, {"status": "Completed", "current_phase": "Done"})
    
    return True