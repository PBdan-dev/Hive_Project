import os
import json
from datetime import datetime
from src.agents.agent_base import AIAgent
from src.core.file_manager import setup_agent_directory, get_template_prompt, load_json, save_json, read_file_content
from src.core.json_validator import validate_team_structure

def format_name(text: str) -> str:
    """Cleans a string to make it a clean identifier (without spaces)"""
    return text.strip().replace(" ", "_").replace("-", "_")

def log_state_milestone(project_name: str, status: str, phase: str, detail: str):
    """Met à jour le statut global et ajoute une ligne d'historique dans state.json avec Timestamp"""
    project_dir = os.path.join("data", project_name)
    state_file = os.path.join(project_dir, "state.json")
    
    current_state = load_json(state_file, {"status": "Initialized", "current_phase": "", "history": []})
    current_state["status"] = status
    current_state["current_phase"] = phase
    
    if "history" not in current_state:
        current_state["history"] = []
        
    current_state["history"].append({
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
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
        raw_json_response = director.ask(message_to_send)
        is_valid, parsed_data, error_message = validate_team_structure(raw_json_response)
        
        if is_valid:
            team_structure = parsed_data
            director.log_validation(success=True)
            break
        else:
            director.log_validation(success=False)
            if attempts < max_retries:
                message_to_send = f"Error: {error_message}\nCorrect your full JSON format."
            else:
                return False, {}

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
            
            log_state_milestone(director.project_name, "In Progress", f"Manager {team} Initialization", f"Manager {manager_name} defined.")
            
            for employee in manager.get("employees", []):
                task = format_name(employee['task_name'])
                employee_name = f"{project}_{team}_{task}_Employee"
                full_employee_prompt = f"{employee_template}\n\nYour Task Role:\n{employee['role']}"
                setup_agent_directory(director.project_name, "employees", employee_name, full_employee_prompt)
                
        return True, team_structure
    except Exception as e:
        print(f"[Workplace Error] : {str(e)}")
        return False, {}

def advance_workflow(project_name: str, current_brief: str) -> bool:
    """
    Machine d'état : Exécute UNE seule tâche atomique puis rend la main.
    Permet à Streamlit de rafraîchir l'interface entre chaque agent.
    Retourne True s'il reste du travail, False si terminé ou en pause.
    """
    project_dir = os.path.join("data", project_name)
    state_file = os.path.join(project_dir, "state.json")
    state = load_json(state_file, {"status": "In Progress", "completed_tasks": [], "history": [], "iteration": 1})

    if state.get("status") != "In Progress":
        return False

    v = state.get("iteration", 1)
    project_name_clean = format_name(project_name)
    
    director_prompt = get_template_prompt("director_preprompt.txt")
    director = AIAgent(
        name=f"{project_name_clean}_Director", role="Director", role_category="director",
        project_name=project_name, system_prompt=director_prompt, model_name="Qwen3.6_27B_Q3:latest"
    )

    # 1. Structure de l'équipe
    team_structure = state.get("team_structure")
    if not team_structure:
        if state.get("active_agent") != director.name:
            state["active_agent"] = director.name
            save_json(state_file, state)
            return True # Rerun UI

        success, ts = generate_team_from_director(director, current_brief)
        if success:
            state = load_json(state_file)
            state["team_structure"] = ts
            state["active_agent"] = None
            save_json(state_file, state)
        else:
            state["status"] = "Error"
            save_json(state_file, state)
        return True

    # 1.5. Mise à jour de la conscience du directeur (Itération > 1)
    if v > 1:
        update_task_id = f"director_update_v{v}"
        if update_task_id not in state.get("completed_tasks", []):
            if state.get("active_agent") != director.name:
                state["active_agent"] = director.name
                save_json(state_file, state)
                return True
                
            log_state_milestone(project_name, "In Progress", f"Director Update v{v}", "Analyzing new scope brief.")
            update_instruction = (
                f"This is Iteration v{v} of the project. The brief has been updated.\n"
                f"New scope/instructions: '{current_brief}'.\n"
                "Review this and prepare to coordinate your managers for this update."
            )
            director.ask(update_instruction)
            
            state = load_json(state_file)
            state["completed_tasks"].append(update_task_id)
            state["active_agent"] = None
            save_json(state_file, state)
            return True

    manager_template = get_template_prompt("manager_preprompt.txt")
    employee_template = get_template_prompt("employee_preprompt.txt")

    # 2. Boucle Opérationnelle
    for manager_data in team_structure.get("managers", []):
        team_name = format_name(manager_data['team_name'])
        manager_name = f"{project_name_clean}_{team_name}_Manager"
        team_context_path = os.path.join(project_dir, "agents_storage", "managers", manager_name, f"team_context_{team_name}.md")

        # A. Employés
        for emp_data in manager_data.get("employees", []):
            task_name = format_name(emp_data['task_name'])
            emp_name = f"{project_name_clean}_{team_name}_{task_name}_Employee"
            task_id_v = f"employee_{emp_name}_v{v}"

            if task_id_v not in state.get("completed_tasks", []):
                # Phase 1: Signaler l'UI
                if state.get("active_agent") != emp_name:
                    state["active_agent"] = emp_name
                    save_json(state_file, state)
                    return True

                # Phase 2: Exécuter
                log_state_milestone(project_name, "In Progress", f"Employee {task_name} (v{v})", f"{emp_name} working.")
                employee_system_prompt = f"{employee_template}\n\nYour Task Role:\n{emp_data['role']}"
                employee_agent = AIAgent(
                    name=emp_name, role=emp_data['role'], role_category="employees",
                    project_name=project_name, system_prompt=employee_system_prompt, model_name=director.model_name
                )
                
                team_context = read_file_content(team_context_path)
                emp_instruction = (
                    f"PROJECT ITERATION: v{v}\n"
                    f"CURRENT PROJECT BRIEF: '{current_brief}'\n\n"
                    f"TEAM CONTEXT & HISTORY:\n{team_context}\n\n"
                    f"YOUR TASK: {emp_data['role']}\n"
                    "Execute your production focusing on current iteration requirements."
                )
                
                emp_result = employee_agent.ask(emp_instruction)
                employee_agent.save_artifact(f"artifact_{emp_name}_v{v}.md", emp_result)
                
                state = load_json(state_file)
                state["completed_tasks"].append(task_id_v)
                state["active_agent"] = None
                save_json(state_file, state)
                return True

        # B. Manager
        mgr_task_id_v = f"manager_{manager_name}_v{v}"
        if mgr_task_id_v not in state.get("completed_tasks", []):
            if state.get("active_agent") != manager_name:
                state["active_agent"] = manager_name
                save_json(state_file, state)
                return True

            log_state_milestone(project_name, "In Progress", f"Manager {team_name} Validation (v{v})", f"{manager_name} aggregating.")
            manager_system_prompt = f"{manager_template}\n\nYour Team Role:\n{manager_data['role']}"
            manager_agent = AIAgent(
                name=manager_name, role=manager_data['role'], role_category="managers",
                project_name=project_name, system_prompt=manager_system_prompt, model_name=director.model_name
            )
            
            team_artifacts = []
            for emp in manager_data.get("employees", []):
                e_name = f"{project_name_clean}_{team_name}_{format_name(emp['task_name'])}_Employee"
                e_path = os.path.join(project_dir, "agents_storage", "employees", e_name, f"artifact_{e_name}_v{v}.md")
                team_artifacts.append(f"--- Task: {emp['task_name']} (Iteration v{v}) ---\n{read_file_content(e_path)}\n")

            mgr_instruction = (
                f"Synthesize and finalize the following outputs from your team for ITERATION v{v}.\n"
                "Ensure coherence with the updated brief.\n\n"
                "Team Productions:\n" + "\n".join(team_artifacts)
            )
            mgr_result = manager_agent.ask(mgr_instruction)
            mgr_filename = f"artifact_{manager_name}_final_v{v}.md"
            manager_agent.save_artifact(mgr_filename, mgr_result)

            # Résumé Context
            summary_instruction = (
                f"Summarize concisely the changes and contributions of this Iteration v{v}.\n"
                "This summary will be added to the team context history for the next iteration.\n\n"
                f"Module v{v}:\n{mgr_result}"
            )
            mgr_summary = manager_agent.ask(summary_instruction)
            with open(team_context_path, 'a', encoding='utf-8') as f:
                f.write(f"\n## Update Iteration v{v}: {mgr_filename}\n{mgr_summary}\n\n")

            state = load_json(state_file)
            state["completed_tasks"].append(mgr_task_id_v)
            state["active_agent"] = None
            save_json(state_file, state)
            return True

    # 3. Director Final
    dir_task_id_v = f"director_final_v{v}"
    if dir_task_id_v not in state.get("completed_tasks", []):
        if state.get("active_agent") != director.name:
            state["active_agent"] = director.name
            save_json(state_file, state)
            return True

        log_state_milestone(project_name, "In Progress", f"Director Final Integration v{v}", "Building final package.")
        all_managers_artifacts = []
        for mgr in team_structure.get("managers", []):
            t_name = format_name(mgr['team_name'])
            m_name = f"{project_name_clean}_{t_name}_Manager"
            m_path = os.path.join(project_dir, "agents_storage", "managers", m_name, f"artifact_{m_name}_final_v{v}.md")
            all_managers_artifacts.append(f"--- Team: {t_name} Module (v{v}) ---\n{read_file_content(m_path)}\n")

        dir_instruction = (
            f"Combine all manager modules into the final deliverable for ITERATION v{v}.\n"
            f"Original/Updated Brief: {current_brief}\n\n"
            "Manager Modules:\n" + "\n".join(all_managers_artifacts)
        )
        final_project_result = director.ask(dir_instruction)
        director.save_artifact(f"artifact_FINAL_PROJECT_OUTPUT_v{v}.md", final_project_result)

        state = load_json(state_file)
        state["completed_tasks"].append(dir_task_id_v)
        state["active_agent"] = None
        state["status"] = "Completed"
        save_json(state_file, state)
        log_state_milestone(project_name, "Completed", f"Iteration v{v} Delivered", f"Integrated all modules.")
        return True

    return False