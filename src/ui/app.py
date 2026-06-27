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
from src.core.workplace import generate_team_from_director, execute_project_workflow
from src.core.file_manager import get_template_prompt

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
                        "name": d, 
                        "brief": "Project loaded from persistent local storage", 
                        "status": state.get("status", "Terminé")
                    })
    return loaded

if "projects" not in st.session_state or not st.session_state.projects:
    st.session_state.projects = load_existing_projects()
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# --- 2. FONCTIONS D'AFFICHAGE DU DASHBOARD ---
def display_agent_card(agent_path, icon):
    """Affiche une carte cliquable pour un agent avec ses stats."""
    agent_name = os.path.basename(agent_path)
    with st.expander(f"{icon} {agent_name}"):
        stats_path = os.path.join(agent_path, "stats.json")
        if os.path.exists(stats_path):
            with open(stats_path, 'r', encoding='utf-8') as f:
                st.json(json.load(f))
        else:
            st.write("No statistics available for this agent yet.")

def display_project_dashboard(proj_name):
    """Génère la vue détaillée d'un projet (Hiérarchie + Fichiers)"""
    st.divider()
    col_hierarchy, col_artifacts = st.columns([2, 1])
    proj_dir = os.path.join(root_dir, "data", proj_name)
    
    with col_hierarchy:
        st.subheader("👥 Team Hierarchy")
        agents_dir = os.path.join(proj_dir, "agents_storage")
        
        # Directeur
        dir_path = os.path.join(agents_dir, "director")
        if os.path.exists(dir_path):
            for d in os.listdir(dir_path): display_agent_card(os.path.join(dir_path, d), "👑")
        
        # Managers
        mgr_path = os.path.join(agents_dir, "managers")
        if os.path.exists(mgr_path):
            for m in os.listdir(mgr_path): display_agent_card(os.path.join(mgr_path, m), "👔")
        
        # Employés
        emp_path = os.path.join(agents_dir, "employees")
        if os.path.exists(emp_path):
            for e in os.listdir(emp_path): display_agent_card(os.path.join(emp_path, e), "👷")

    with col_artifacts:
        st.subheader("📄 State & Output Artifacts")
        
        # État du projet
        state_file = os.path.join(proj_dir, "state.json")
        if os.path.exists(state_file):
            with st.expander("📊 state.json (Live Execution Log)", expanded=True):
                with open(state_file, 'r', encoding='utf-8') as f:
                    st.json(json.load(f))
                    
        # Filtrage strict et affichage des productions (commençant par artifact_)
        for root_path, _, files in os.walk(proj_dir):
            for file in files:
                if file.startswith("artifact_") and file.endswith(".md"):
                    parent_folder = os.path.basename(root_path)
                    with st.expander(f"📝 {file} ({parent_folder})"):
                        with open(os.path.join(root_path, file), 'r', encoding='utf-8') as f:
                            st.markdown(f.read())

# --- 3. FONCTION DE LANCEMENT DU PROJET ---
def run_project_initialization(proj_name, proj_brief):
    with st.status(f"🚀 Initializing {proj_name}...", expanded=True) as status:
        status.write("Loading Director template...")
        director_prompt = get_template_prompt("director_preprompt.txt")
        
        if "Error" in director_prompt:
            st.error(director_prompt)
            return
        
        status.write("Instantiating Director Agent...")
        director = AIAgent(
            name=f"{proj_name}_Director", role="Director", role_category="director",
            project_name=proj_name, system_prompt=director_prompt, model_name="Qwen3.6_27B_Q3:latest"
        )
        
        status.write("Director is analyzing brief and hiring managers...")
        success, team_structure = generate_team_from_director(director, proj_brief)
        
        if success:
            status.write("Team created. Launching autonomous execution sequence...")
            execute_project_workflow(director, team_structure, proj_brief)
            status.update(label="✅ Project Completed!", state="complete", expanded=False)
            
            # Recharger instantanément la liste globale
            st.session_state.projects = load_existing_projects()
        else:
            status.update(label="❌ Team Generation Failed.", state="error")
            st.error("The Director failed to produce a valid team structure. Check local logs.")

# --- 4. POP-UP : CRÉATION ---
@st.dialog("Create New Project")
def create_project_dialog():
    st.write("Enter project details to start the autonomous cycle.")
    proj_name = st.text_input("Project Name (no spaces)", placeholder="Project_Zeta")
    proj_brief = st.text_area("Project Brief", placeholder="Describe exactly what you want the Hive to build...")
    
    if st.button("Launch Hierarchy", type="primary"):
        if proj_name and proj_brief: run_project_initialization(proj_name, proj_brief)
        else: st.warning("Please fill all fields.")

# --- 5. STRUCTURE PRINCIPALE ---
tab_chat, tab_projects = st.tabs(["💬 Global Chat", "📁 Projects Management"])

with tab_projects:
    st.header("Active Hives")
    if st.button("➕ Start New Project"):
        create_project_dialog()
    
    st.divider()
    
    if not st.session_state.projects:
        st.info("No active projects. Start one to see the directory structure.")
    else:
        for p in st.session_state.projects:
            with st.expander(f"📦 {p['name']} - {p['status']}", expanded=False):
                st.write(f"**Objective:** {p['brief']}")
                if st.button("Ouvrir le Dashboard", key=f"dash_{p['name']}"):
                    display_project_dashboard(p['name'])

with tab_chat:
    st.header("Hive Communication")
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]): st.write(msg["content"])
            
    if prompt := st.chat_input("Send command..."):
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        st.chat_message("user").write(prompt)