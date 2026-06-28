import streamlit as st
import os
import sys
import json
import time

# Configuration des chemins
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, "../../"))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.core.workplace import format_name, advance_workflow
from src.core.file_manager import load_json, save_json

st.set_page_config(page_title="Hive Project - AI Management", layout="wide")

# --- LECTURE DES DONNÉES LOCALES ---
def load_existing_projects():
    """Lit le dossier data/ pour restaurer les projets au lancement."""
    loaded = []
    data_dir = os.path.join(root_dir, "data")
    if os.path.exists(data_dir):
        for d in os.listdir(data_dir):
            state_path = os.path.join(data_dir, d, "state.json")
            if os.path.exists(state_path):
                state = load_json(state_path)
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

# --- AFFICHAGE COMPOSANTS ---
def display_agent_card(agent_path, icon, is_active=False):
    agent_name = os.path.basename(agent_path)
    
    if is_active:
        st.markdown(f"**🟢 [ACTIVE] {icon} {agent_name} is processing...**")
    else:
        st.markdown(f"**{icon} {agent_name}**")
    
    with st.expander("System Specs & Live Prompts", expanded=is_active):
        stats_path = os.path.join(agent_path, "stats.json")
        if os.path.exists(stats_path):
            st.json(load_json(stats_path, {}))
        else:
            st.write("No statistics available.")
            
        # Affichage avec clés (key) uniques basées sur le nom de l'agent
        last_prompt_path = os.path.join(agent_path, "last_full_prompt.txt")
        if os.path.exists(last_prompt_path):
            with open(last_prompt_path, 'r', encoding='utf-8') as f:
                st.text_area("Last Full Interaction (System + History + User Instruction)", f.read(), height=250, disabled=True, key=f"full_prompt_{agent_name}")
        else:
            prompt_path = os.path.join(agent_path, "system_prompt.txt")
            if os.path.exists(prompt_path):
                with open(prompt_path, 'r', encoding='utf-8') as f:
                    st.text_area("Base System Prompt", f.read(), height=150, disabled=True, key=f"base_prompt_{agent_name}")


def display_project_dashboard(proj_id):
    proj_dir = os.path.join(root_dir, "data", proj_id)
    state_file = os.path.join(proj_dir, "state.json")
    state = load_json(state_file, {})
    
    st.divider()
    if st.button("❌ Close Dashboard"):
        del st.session_state["active_dashboard"]
        st.rerun()

    # Métadonnées
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
        st.success("Metadata updated!")
        st.session_state.projects = load_existing_projects()
        st.rerun()

    # Statut
    st.write(f"**Execution State :** `{state.get('status')}` | **Phase :** `{state.get('current_phase')}` | **Iteration :** `v{state.get('iteration', 1)}`")
    col_run, col_pause = st.columns(2)
    
    with col_run:
        if state.get("status") in ["Initialized", "Paused", "Error"]:
            if st.button("▶️ Start / Resume Engine", key=f"run_btn_{proj_id}", type="primary"):
                state["status"] = "In Progress"
                save_json(state_file, state)
                st.session_state.projects = load_existing_projects()
                st.rerun()
        elif state.get("status") == "Completed":
            if st.button("🔄 Start New Iteration (Update Project)", key=f"restart_btn_{proj_id}", type="primary"):
                state["iteration"] = state.get("iteration", 1) + 1
                state["status"] = "In Progress"
                save_json(state_file, state)
                st.rerun()
                
    with col_pause:
        if state.get("status") == "In Progress":
            if st.button("⏸️ Request Pause", key=f"pause_btn_{proj_id}"):
                state["status"] = "Paused"
                save_json(state_file, state)
                st.warning("Pausing workflow...")
                st.rerun()

    st.divider()
    
    active_agent = state.get("active_agent", None)
    team_structure = state.get("team_structure", {})

    st.subheader("🏢 Visual Hierarchy & Live Team")
    if not team_structure:
        st.info("Team structure not generated yet. Start the engine to initialize.")
        dir_path = os.path.join(proj_dir, "agents_storage", "director", f"{proj_id}_Director")
        if os.path.exists(dir_path):
            display_agent_card(dir_path, "👑", is_active=(active_agent == f"{proj_id}_Director"))
    else:
        col_space1, col_dir, col_space2 = st.columns([1, 2, 1])
        with col_dir:
            dir_name = f"{proj_id}_Director"
            dir_path = os.path.join(proj_dir, "agents_storage", "director", dir_name)
            display_agent_card(dir_path, "👑", is_active=(active_agent == dir_name))
        
        st.write("---")
        
        managers = team_structure.get("managers", [])
        if managers:
            cols = st.columns(len(managers))
            for i, mgr in enumerate(managers):
                with cols[i]:
                    team = format_name(mgr['team_name'])
                    mgr_name = f"{proj_id}_{team}_Manager"
                    mgr_path = os.path.join(proj_dir, "agents_storage", "managers", mgr_name)
                    
                    st.markdown(f"#### 👔 Team {team}")
                    display_agent_card(mgr_path, "👔", is_active=(active_agent == mgr_name))
                    
                    for emp in mgr.get("employees", []):
                        task = format_name(emp['task_name'])
                        emp_name = f"{proj_id}_{team}_{task}_Employee"
                        emp_path = os.path.join(proj_dir, "agents_storage", "employees", emp_name)
                        
                        display_agent_card(emp_path, "👷", is_active=(active_agent == emp_name))

    st.divider()
    st.subheader("📄 Generated Files & Logs")
    col_files, col_logs = st.columns(2)
    
    with col_files:
        for root_path, _, files in os.walk(proj_dir):
            for file in sorted(files, reverse=True):
                if (file.startswith("artifact_") or file.startswith("team_context_")) and file.endswith(".md"):
                    with st.expander(f"📝 {file}"):
                        with open(os.path.join(root_path, file), 'r', encoding='utf-8') as f:
                            st.markdown(f.read())
                            
    with col_logs:
        with st.expander("⏱️ Timestamps & Project History", expanded=True):
            history = state.get("history", [])
            for h in history[::-1]:
                st.markdown(f"`[{h.get('timestamp', 'Init')}]` **{h.get('phase')}** : {h.get('detail')}")

    # --- EXECUTION BACKGROUND (Triggered after UI render) ---
    is_running = state.get("status") == "In Progress"
    if is_running:
        with st.spinner("AI Hive is processing in background..."):
            needs_rerun = advance_workflow(proj_id, state.get("brief", ""))
        
        if needs_rerun:
            time.sleep(0.5) # Petit délai pour laisser l'interface souffler
            st.rerun()


# --- DIALOG CREATION ---
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
            
            state_file = os.path.join(proj_dir, "state.json")
            initial_state = {
                "display_name": proj_name,
                "brief": proj_brief,
                "status": "Initialized",
                "current_phase": "Initialization",
                "completed_tasks": [],
                "history": [],
                "iteration": 1
            }
            save_json(state_file, initial_state)
            
            st.session_state.projects = load_existing_projects()
            st.rerun()
        else:
            st.warning("Please populate both fields.")

# --- PAGE ---
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
                    st.rerun()
                    
        if "active_dashboard" in st.session_state:
            display_project_dashboard(st.session_state["active_dashboard"])

with tab_chat:
    st.header("Hive Communication")
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]): st.write(msg["content"])
    if prompt := st.chat_input("Send command..."):
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        st.chat_message("user").write(prompt)