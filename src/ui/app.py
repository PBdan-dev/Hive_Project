import streamlit as st
import os
import sys
import json

# Configuration des chemins
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, "../../"))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.agents.agent_base import AIAgent
from src.core.workplace import generate_team_from_director, execute_project_workflow, format_name
from src.core.file_manager import get_template_prompt, load_json, save_json

st.set_page_config(page_title="Hive Project - AI Management", layout="wide")

# --- 1. LECTURE DES DONNÉES LOCALES ---
def load_existing_projects():
    """Lit le dossier data/ pour restaurer les projets au lancement."""
    loaded = []
    data_dir = os.path.join(root_dir, "data")
    if os.path.exists(data_dir):
        for d in os.listdir(data_dir):
            state_path = os.path.join(data_dir, d, "state.json")
            if os.path.exists(state_path):
                with open(state_path, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                    loaded.append({
                        "id": d,
                        "name": state.get("display_name", d), 
                        "brief": state.get("brief", ""), 
                        "status": state.get("status", "Initialized")
                    })
    return loaded

if "projects" not in st.session_state or not st.session_state.projects:
    st.session_state.projects = load_existing_projects()
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# --- 2. EXECUTION LIVE DEPUIS LE DASHBOARD ---
def run_live_workflow(proj_id, brief):
    """Exécute l'étape suivante du projet en direct dans l'interface"""
    state_file = os.path.join(root_dir, "data", proj_id, "state.json")
    state = load_json(state_file)
    
    # Forcer le statut de reprise
    state["status"] = "In Progress"
    save_json(state_file, state)
    
    with st.status(f"Running execution layer for {proj_id}...", expanded=True) as status:
        director_prompt = get_template_prompt("director_preprompt.txt")
        director = AIAgent(
            name=f"{proj_id}_Director", role="Director", role_category="director",
            project_name=proj_id, system_prompt=director_prompt, model_name="Qwen3.6_27B_Q3:latest"
        )
        
        team_structure = state.get("team_structure", None)
        if not team_structure:
            status.write("Director is structuring teams & hiring managers...")
            success, team_structure = generate_team_from_director(director, brief)
            if success:
                state = load_json(state_file)
                state["team_structure"] = team_structure
                save_json(state_file, state)
            else:
                status.update(label="❌ Structure synthesis failed.", state="error")
                return

        status.write("Processing operational agent tasks...")
        execute_project_workflow(director, team_structure, brief)
        
        final_state = load_json(state_file)
        if final_state.get("status") == "Paused":
            status.update(label="⏸️ Execution successfully paused.", state="warning")
        else:
            status.update(label="✅ Cycle execution block finalized!", state="complete")

# --- 3. DASHBOARD GRAPHIQUE ---
def display_agent_card(agent_path, icon):
    agent_name = os.path.basename(agent_path)
    with st.expander(f"{icon} {agent_name}"):
        stats_path = os.path.join(agent_path, "stats.json")
        if os.path.exists(stats_path):
            with open(stats_path, 'r', encoding='utf-8') as f:
                st.json(json.load(f))
        else:
            st.write("No statistics available.")

def display_project_dashboard(proj_id):
    """Génère l'affichage dynamique (Modifications + Hiérarchie + Artifacts)"""
    proj_dir = os.path.join(root_dir, "data", proj_id)
    state_file = os.path.join(proj_dir, "state.json")
    state = load_json(state_file)
    
    st.divider()
    
    # Édition des métadonnées sous le projet
    st.subheader("⚙️ Project Configuration")
    col_name, col_brief = st.columns([1, 2])
    with col_name:
        new_name = st.text_input("Project Display Name", value=state.get("display_name", proj_id), key=f"name_{proj_id}")
    with col_brief:
        new_brief = st.text_area("Scope Brief & Extra Instructions", value=state.get("brief", ""), key=f"desc_{proj_id}")
        
    if st.button("💾 Save Project Updates", key=f"save_{proj_id}"):
        state["display_name"] = new_name
        state["brief"] = new_brief
        save_json(state_file, state)
        st.success("Metadata and prompt changes recorded!")
        st.session_state.projects = load_existing_projects()
        st.rerun()

    # Boutons d'action : Pause / Reprise / Lancement
    st.write(f"**Execution State :** `{state.get('status')}` | **Phase :** `{state.get('current_phase')}`")
    col_run, col_pause = st.columns(2)
    with col_run:
        if state.get("status") in ["Initialized", "Paused"]:
            if st.button("▶️ Start / Resume Engine", key=f"run_btn_{proj_id}", type="primary"):
                run_live_workflow(proj_id, state.get("brief"))
                st.session_state.projects = load_existing_projects()
                st.rerun()
    with col_pause:
        if state.get("status") == "In Progress":
            if st.button("⏸️ Request Pause", key=f"pause_btn_{proj_id}"):
                state["status"] = "Paused"
                save_json(state_file, state)
                st.warning("The system will suspend operations after completing the current atomic agent task.")
                st.rerun()

    st.divider()
    col_hierarchy, col_artifacts = st.columns([2, 1])
    
    with col_hierarchy:
        st.subheader("👥 Live Team Layout")
        agents_dir = os.path.join(proj_dir, "agents_storage")
        
        for cat, icon in [("director", "👑"), ("managers", "👔"), ("employees", "**👷**")]:
            path = os.path.join(agents_dir, cat)
            if os.path.exists(path):
                for a in os.listdir(path): display_agent_card(os.path.join(path, a), icon)

    with col_artifacts:
        st.subheader("📄 Generated Artifacts")
        if os.path.exists(state_file):
            with st.expander("📊 state.json (System Log)", expanded=False):
                st.json(load_json(state_file))
                    
        for root_path, _, files in os.walk(proj_dir):
            for file in files:
                if file.startswith("artifact_") and file.endswith(".md"):
                    with st.expander(f"📝 {file}"):
                        with open(os.path.join(root_path, file), 'r', encoding='utf-8') as f:
                            st.markdown(f.read())

# --- 4. POP-UP DE CREATION (Flux corrigé) ---
@st.dialog("Create New Project")
def create_project_dialog():
    st.write("Initialize workspace parameters.")
    proj_name = st.text_input("Project Folder ID (No spaces)", placeholder="Project_Delta")
    proj_brief = st.text_area("Initial Project Brief")
    
    if st.button("Launch Structure Initialization", type="primary"):
        if proj_name and proj_brief:
            cleaned_id = format_name(proj_name)
            proj_dir = os.path.join(root_dir, "data", cleaned_id)
            os.makedirs(proj_dir, exist_ok=True)
            
            # Initialisation de la structure de base
            state_file = os.path.join(proj_dir, "state.json")
            initial_state = {
                "display_name": proj_name,
                "brief": proj_brief,
                "status": "Initialized",
                "current_phase": "Team Layout Mapping",
                "completed_tasks": [],
                "history": []
            }
            save_json(state_file, initial_state)
            
            # Rechargement et fermeture automatique de la fenêtre
            st.session_state.projects = load_existing_projects()
            st.rerun()
        else:
            st.warning("Please populate both fields.")

# --- 5. STRUCTURE DE LA PAGE ---
tab_chat, tab_projects = st.tabs(["💬 Global Chat", "📁 Projects Management"])

with tab_projects:
    st.header("Active Hives")
    if st.button("➕ Start New Project"): create_project_dialog()
    
    st.divider()
    
    if not st.session_state.projects:
        st.info("No active projects. Start one to see the directory structure.")
    else:
        for p in st.session_state.projects:
            with st.expander(f"📦 {p['name']} — Status: `{p['status']}`", expanded=False):
                st.write(f"**Original Brief Summary:** {p['brief'][:150]}...")
                if st.button("Open Control Dashboard", key=f"dash_{p['id']}"):
                    st.session_state["active_dashboard"] = p['id']
                    
        if "active_dashboard" in st.session_state:
            display_project_dashboard(st.session_state["active_dashboard"])

with tab_chat:
    st.header("Hive Communication")
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]): st.write(msg["content"])
    if prompt := st.chat_input("Send command..."):
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        st.chat_message("user").write(prompt)