import time
import json
import os
from ollama import Client  # Specific Client import
from src.core.file_manager import setup_agent_directory, save_json, load_json

class AIAgent:
    def __init__(self, name: str, role: str, role_category: str, project_name: str, system_prompt: str, model_name: str):
        self.name = name
        self.role = role
        self.role_category = role_category
        self.project_name = project_name
        self.model_name = model_name
        self.system_prompt = system_prompt

        # 1. Explicit client configuration (Forces IPv4)
        self.client = Client(host='http://127.0.0.1:11434')

        # 2. Preparation of the directory structure and files
        self.agent_dir = setup_agent_directory(project_name, role_category, name, system_prompt)
        self.stats_file = os.path.join(self.agent_dir, "stats.json")
        self.memory_file = os.path.join(self.agent_dir, "memory.json")

        # 3. Loading existing data (persistence)
        self.stats = load_json(self.stats_file, {})
        self.memory = load_json(self.memory_file, [])

    def save_state(self):
        """Saves memory and statistics to disk"""
        save_json(self.stats_file, self.stats)
        save_json(self.memory_file, self.memory)

    def ask(self, user_message: str) -> str:
        """Sends the task to Ollama via the explicit client"""
        start_time = time.time()
        self.stats["tasks_started"] += 1

        messages = [{"role": "system", "content": self.system_prompt}]
        messages.extend(self.memory)
        messages.append({"role": "user", "content": user_message})

        try:
            # Use of self.client instead of global ollama
            response = self.client.chat(model=self.model_name, messages=messages)
            
            end_time = time.time()
            duration = end_time - start_time
            reply_content = response['message']['content']
            tokens = response.get('eval_count', 0)

            self.stats["tokens_produced"] += tokens
            self.stats["total_work_time_sec"] += duration
            self.stats["average_time_per_task_sec"] = self.stats["total_work_time_sec"] / self.stats["tasks_started"]

            self.memory.append({"role": "user", "content": user_message})
            self.memory.append({"role": "assistant", "content": reply_content})

            self.save_state()
            return reply_content

        except Exception as e:
            self.save_state()
            return f"Critical error for agent {self.name}: {str(e)}"

    def log_validation(self, success: bool):
        """Called to validate or reject the work"""
        if success:
            self.stats["tasks_validated"] += 1
        else:
            self.stats["tasks_failed"] += 1
        self.save_state()

    def save_artifact(self, filename: str, content: str) -> str:
        """Saves a validated production in the agent's dedicated folder."""
        filepath = os.path.join(self.agent_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return filepath