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
    
    manager_template = get_template_prompt("manager_preprompt.txt")
    employee_template = get_template_prompt("employee_preprompt.txt")
    
    try:
        for manager in team_structure.get("managers", []):
            team = format_name(manager['team_name'])
            manager_name = f"{project}_{team}_Manager"
            
            full_manager_prompt = f"{manager_template}\n\nYour Team Role:\n{manager['role']}"
            setup_agent_directory(director.project_name, "managers", manager_name, full_manager_prompt)
            team_context_path = os.path.join("data", project, "agents_storage", "managers", manager_name, f"team_context_{team}.md")
            with open(team_context_path, 'w', encoding='utf-8') as f:
                f.write(f"# Context for Team {team}\n\n")
            print(f" -> Created: {manager_name}")
            
            log_state_milestone(
                director.project_name, "In Progress", f"Manager {team} Initialization", 
                f"Manager {manager_name} defined the sub-tasks for their team."
            )
            
            for employee in manager.get("employees", []):
                task = format_name(employee['task_name'])
                employee_name = f"{project}_{team}_{task}_Employee"
                
                full_employee_prompt = f"{employee_template}\n\nYour Task Role:\n{employee['role']}"
                setup_agent_directory(director.project_name, "employees", employee_name, full_employee_prompt)
                print(f"    -> Created: {employee_name}")
                
        print("\n[Workplace] : Nomenclature applied successfully in /data!")
        return True, team_structure
    except Exception as e:
        print(f"[Workplace Error] : {str(e)}")
        return False, {}


def execute_project_workflow(director: AIAgent, team_structure: dict, project_brief: str):
    """Exécute la production de A à Z avec support Pause/Reprise et Itérations (Versioning)"""
    project_dir = os.path.join("data", director.project_name)
    state_file = os.path.join(project_dir, "state.json")

    # Chargement de l'état actuel
    state = load_json(state_file, {"status": "In Progress", "completed_tasks": [], "history": [], "iteration": 1})
    if state.get("status") == "Paused":
        return True
    
    # 1. Gestion du Versioning et du Brief
    v = state.get("iteration", 1)
    current_brief = state.get("brief", project_brief) # Utilise le brief potentiellement modifié dans l'UI
    
    log_state_milestone(director.project_name, "In Progress", f"Execution v{v} Started", f"Processing loop for iteration {v}.")
    
    # --- CONSCIENCE DU DIRECTEUR (Si Itération > 1) ---
    if v > 1:
        # On informe le directeur des nouvelles instructions avant de lancer les équipes
        update_milestone = f"Director analyzing update v{v}"
        if update_milestone not in [h["phase"] for h in state.get("history", [])]:
            log_state_milestone(director.project_name, "In Progress", update_milestone, "Updating Director memory with new scope brief.")
            update_instruction = (
                f"This is Iteration v{v} of the project. The brief has been updated.\n"
                f"New scope/instructions: '{current_brief}'.\n"
                "Review this and prepare to coordinate your managers for this update."
            )
            director.ask(update_instruction)

    project_name_clean = format_name(director.project_name)
    all_managers_artifacts = []

    manager_template = get_template_prompt("manager_preprompt.txt")
    employee_template = get_template_prompt("employee_preprompt.txt")

    # 2. Boucle Opérationnelle
    for manager_data in team_structure.get("managers", []):
        # Vérification Pause entre les managers
        state = load_json(state_file)
        if state.get("status") == "Paused": return True

        team_name = format_name(manager_data['team_name'])
        manager_name = f"{project_name_clean}_{team_name}_Manager"
        manager_system_prompt = f"{manager_template}\n\nYour Team Role:\n{manager_data['role']}"
        
        manager_agent = AIAgent(
            name=manager_name, role=manager_data['role'], role_category="managers",
            project_name=director.project_name, system_prompt=manager_system_prompt, 
            model_name=director.model_name
        )
        
        team_artifacts = []
        team_context_path = os.path.join(project_dir, "agents_storage", "managers", manager_name, f"team_context_{team_name}.md")
        
        # A. BOUCLE EMPLOYÉS
        for emp_data in manager_data.get("employees", []):
            # Vérification Pause entre les employés
            state = load_json(state_file)
            if state.get("status") == "Paused": return True

            task_name = format_name(emp_data['task_name'])
            emp_name = f"{project_name_clean}_{team_name}_{task_name}_Employee"
            
            # --- VERSIONING DES TÂCHES ET ARTIFACTS ---
            task_id_v = f"employee_{emp_name}_v{v}"
            artifact_filename_v = f"artifact_{emp_name}_v{v}.md"
            
            # Récupération de l'artifact existant si déjà complété pour CETTE version
            emp_artifact_path = os.path.join(project_dir, "agents_storage", "employees", emp_name, artifact_filename_v)
            
            if task_id_v in state.get("completed_tasks", []) and os.path.exists(emp_artifact_path):
                with open(emp_artifact_path, 'r', encoding='utf-8') as f:
                    emp_result = f.read()
                team_artifacts.append(f"--- Task: {task_name} (Iteration v{v}) ---\n{emp_result}\n")
                continue
            
            log_state_milestone(director.project_name, "In Progress", f"Employee {task_name} Working (v{v})", f"Employee {emp_name} processing iteration {v}.")
            
            employee_system_prompt = f"{employee_template}\n\nYour Task Role:\n{emp_data['role']}"
            employee_agent = AIAgent(
                name=emp_name, role=emp_data['role'], role_category="employees",
                project_name=director.project_name, system_prompt=employee_system_prompt, 
                model_name=director.model_name
            )
            
            # --- LECTURE DU TEAM CONTEXT ---
            team_context = ""
            if os.path.exists(team_context_path):
                with open(team_context_path, 'r', encoding='utf-8') as f:
                    team_context = f.read()

            # Instruction incluant Itération, Brief à jour et Contexte d'équipe
            emp_instruction = (
                f"PROJECT ITERATION: v{v}\n"
                f"CURRENT PROJECT BRIEF: '{current_brief}'\n\n"
                f"TEAM CONTEXT & HISTORY:\n{team_context}\n\n"
                f"YOUR TASK: {emp_data['role']}\n"
                "Execute your production focusing on current iteration requirements."
            )
            
            emp_result = employee_agent.ask(emp_instruction)
            employee_agent.save_artifact(artifact_filename_v, emp_result)
            team_artifacts.append(f"--- Task: {task_name} (Iteration v{v}) ---\n{emp_result}\n")
            
            # Enregistrement de la tâche accomplie (versionnée)
            state = load_json(state_file)
            if "completed_tasks" not in state: state["completed_tasks"] = []
            state["completed_tasks"].append(task_id_v)
            save_json(state_file, state)
            
            log_state_milestone(director.project_name, "In Progress", f"Employee {task_name} Done (v{v})", f"Employee {emp_name} finalized production for v{v}.")
            
        # B. ACTION MANAGER (Validation et Agrégation v{v})
        state = load_json(state_file)
        if state.get("status") == "Paused": return True
        
        mgr_task_id_v = f"manager_{manager_name}_v{v}"
        mgr_artifact_filename_v = f"artifact_{manager_name}_final_v{v}.md"
        mgr_artifact_path = os.path.join(project_dir, "agents_storage", "managers", manager_name, mgr_artifact_filename_v)
        
        if mgr_task_id_v in state.get("completed_tasks", []) and os.path.exists(mgr_artifact_path):
            with open(mgr_artifact_path, 'r', encoding='utf-8') as f:
                mgr_result = f.read()
            all_managers_artifacts.append(f"--- Team: {team_name} Module (v{v}) ---\n{mgr_result}\n")
        else:
            log_state_milestone(director.project_name, "In Progress", f"Manager {team_name} Validation (v{v})", f"Manager {manager_name} aggregating v{v} productions.")
            
            mgr_instruction = (
                f"Synthesize and finalize the following outputs from your team for ITERATION v{v}.\n"
                "Ensure coherence with the updated brief.\n\n"
                "Team Productions:\n" + "\n".join(team_artifacts)
            )
            mgr_result = manager_agent.ask(mgr_instruction)
            
            manager_agent.save_artifact(mgr_artifact_filename_v, mgr_result)
            all_managers_artifacts.append(f"--- Team: {team_name} Module (v{v}) ---\n{mgr_result}\n")
            
            # --- MISE À JOUR DU TEAM CONTEXT (Résumé itératif) ---
            summary_instruction = (
                f"Summarize concisely the changes and contributions of this Iteration v{v}.\n"
                "This summary will be added to the team context history for the next iteration.\n\n"
                f"Module v{v}:\n{mgr_result}"
            )
            mgr_summary = manager_agent.ask(summary_instruction)
            
            if os.path.exists(team_context_path):
                with open(team_context_path, 'a', encoding='utf-8') as f:
                    f.write(f"## Update Iteration v{v}: {mgr_artifact_filename_v}\n{mgr_summary}\n\n")
            
            state = load_json(state_file)
            state["completed_tasks"].append(mgr_task_id_v)
            save_json(state_file, state)
            
            log_state_milestone(director.project_name, "In Progress", f"Manager {team_name} Done (v{v})", f"Manager {manager_name} completed module v{v}.")

    # 3. Action Directeur Finale (Package final v{v})
    state = load_json(state_file)
    if state.get("status") == "Paused": return True
    
    dir_task_id_v = f"director_final_v{v}"
    if dir_task_id_v not in state.get("completed_tasks", []):
        log_state_milestone(director.project_name, "In Progress", f"Director Final Integration v{v}", f"Director {director.name} building the package for v{v}.")
        
        dir_instruction = (
            f"Combine all manager modules into the final deliverable for ITERATION v{v}.\n"
            f"Original/Updated Brief: {current_brief}\n\n"
            "Manager Modules:\n" + "\n".join(all_managers_artifacts)
        )
        final_project_result = director.ask(dir_instruction)
        
        director.save_artifact(f"artifact_FINAL_PROJECT_OUTPUT_v{v}.md", final_project_result)
        
        state = load_json(state_file)
        state["completed_tasks"].append(dir_task_id_v)
        state["status"] = "Completed" # Marquer comme complété pour cette version
        save_json(state_file, state)
        
        log_state_milestone(director.project_name, "Completed", f"Iteration v{v} Delivered", f"Director integrated all modules for version {v}.")
    
    return True