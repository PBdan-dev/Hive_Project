import streamlit as st
import os
import sys

# Ajout du chemin racine pour les imports si nécessaire
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, "../../"))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# Imports du Backend
from src.agents.agent_base import AIAgent
from src.core.workplace import generate_team_from_director, execute_project_workflow
from src.core.file_manager import get_template_prompt

# Configuration de la page
st.set_page_config(page_title="Hive Project - AI Management", layout="wide")

# Initialisation du Session State
if "projects" not in st.session_state:
    st.session_state.projects = []
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# --- 1. FONCTION DE LANCEMENT DU PROJET ---
def run_project_initialization(proj_name, proj_brief):
    """Lance la création du directeur et de l'équipe"""
    with st.status(f"🚀 Initializing {proj_name}...", expanded=True) as status:
        # 1. Chargement du Prompt
        status.write("Loading Director template...")
        # Ciblage du fichier director_preprompt.txt
        director_prompt = get_template_prompt("director_preprompt.txt")
        
        if "Error" in director_prompt:
            st.error(director_prompt)
            return
        
        # 2. Création du Directeur
        status.write("Instantiating Director Agent...")
        director = AIAgent(
            name=f"{proj_name}_Director", 
            role="Director", 
            role_category="director",
            project_name=proj_name,
            system_prompt=director_prompt, 
            model_name="Qwen3.6_27B_Q3:latest"
        )
        
        # 3. Génération de l'équipe (L'IA réfléchit ici)
        status.write("Director is analyzing brief and hiring managers...")
        success, team_structure = generate_team_from_director(director, proj_brief)
        
        if success:
            status.write("Team created. Launching autonomous execution sequence...")
            
            # Lancement de la nouvelle boucle de travail de A à Z
            execute_project_workflow(director, team_structure, proj_brief)
            
            status.update(label="✅ Project Completed!", state="complete", expanded=False)
            st.session_state.projects.append({
                "name": proj_name, 
                "brief": proj_brief,
                "status": "Completed"
            })
        else:
            status.update(label="❌ Team Generation Failed.", state="error")
            st.error("The Director failed to produce a valid team structure. Check local logs.")

# --- 2. POP-UP : Création de projet ---
@st.dialog("Create New Project")
def create_project_dialog():
    st.write("Enter project details to start the autonomous cycle.")
    proj_name = st.text_input("Project Name (no spaces)", placeholder="Project_Zeta")
    proj_brief = st.text_area("Project Brief", placeholder="Describe exactly what you want the Hive to build...")
    
    if st.button("Launch Hierarchy", type="primary"):
        if proj_name and proj_brief:
            run_project_initialization(proj_name, proj_brief)
        else:
            st.warning("Please fill all fields.")

# --- 3. STRUCTURE PRINCIPALE ---
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
            with st.expander(f"📦 {p['name']} - {p['status']}"):
                st.write(f"**Objective:** {p['brief']}")
                st.info(f"Files created in: `data/{p['name']}/`")

with tab_chat:
    st.header("Hive Communication")
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]): st.write(msg["content"])
            
    if prompt := st.chat_input("Send command..."):
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        st.chat_message("user").write(prompt)