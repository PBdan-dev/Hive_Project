import json
import re

def clean_json_string(raw_str: str) -> str:
    """Removes any Markdown tags around the JSON."""
    if "```json" in raw_str:
        return raw_str.split("```json")[1].split("```")[0].strip()
    elif "```" in raw_str:
        return raw_str.split("```")[1].split("```")[0].strip()
    return raw_str.strip()

def verify_agent_constraints(name: str, role: str) -> tuple[bool, str]:
    """Deterministic test of text limits and format."""
    if not isinstance(name, str) or not isinstance(role, str):
        return False, "Name and role must be text."
    
    # Length validation
    if len(name) < 2 or len(name) > 30:
        return False, f"Name too long or too short ({len(name)} characters). Expected: 2-30."
    if len(role) < 10 or len(role) > 500:
        return False, f"Role too short or too long ({len(role)} characters). Expected: 10-500."
    
    # Strict prohibition of HTML or XML tags
    if re.search(r"<[^>]*>", name) or re.search(r"<[^>]*>", role):
        return False, "Presence of forbidden HTML/XML tags."
        
    return True, ""

def validate_team_structure(raw_response: str) -> tuple[bool, dict, str]:
    """Validates the integrity of the AI response with the new team and task keys."""
    clean_str = clean_json_string(raw_response)
    
    try:
        data = json.loads(clean_str)
    except json.JSONDecodeError as e:
        return False, {}, f"Invalid JSON: {str(e)}"
    
    if not isinstance(data, dict) or "managers" not in data:
        return False, {}, "The root key 'managers' is missing or invalid."

    for i, manager in enumerate(data["managers"]):
        if not all(k in manager for k in ("team_name", "role", "employees")):
            return False, {}, f"Manager {i} is missing keys (team_name, role, employees)."
        
        valid, msg = verify_agent_constraints(manager["team_name"], manager["role"])
        if not valid:
            return False, {}, f"Team '{manager.get('team_name', '')}' invalid: {msg}"

        for j, employee in enumerate(manager["employees"]):
            if not all(k in employee for k in ("task_name", "role")):
                return False, {}, f"Employee {j} of team '{manager['team_name']}' is missing keys."
            
            valid, msg = verify_agent_constraints(employee["task_name"], employee["role"])
            if not valid:
                return False, {}, f"Task '{employee.get('task_name', '')}' invalid: {msg}"

    return True, data, "Validation successful"