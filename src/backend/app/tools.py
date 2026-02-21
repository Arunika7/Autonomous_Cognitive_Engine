
from typing import Dict, Any, List
import json
from datetime import datetime
from backend.app.utils import AgentState


class ToolExecutor:

    # ──────────────────────────────────────────────────────────────────────────────
    #  Virtual File System Tools
    # ──────────────────────────────────────────────────────────────────────────────

    @staticmethod
    def list_files(state: AgentState, **kwargs) -> Dict[str, Any]:
        """List all files in the virtual file system"""
        files = state.get("files", {})
        if not files:
            return {"success": True, "summary": "No files exist yet", "result": []}

        file_list = [
            f"• {name} ({len(content)} chars)"
            for name, content in sorted(files.items())
        ]
        summary = f"Found {len(files)} file(s):\n" + "\n".join(file_list)
        return {
            "success": True,
            "summary": summary,
            "result": list(files.keys())
        }

    @staticmethod
    def read_file(state: AgentState, filename: str, **kwargs) -> Dict[str, Any]:
        """Read the full content of a file"""
        files = state.get("files", {})
        if filename not in files:
            return {"success": False, "summary": f"File not found: {filename}"}

        content = files[filename]
        preview = content[:120] + "..." if len(content) > 120 else content
        return {
            "success": True,
            "summary": f"Read {filename} ({len(content)} characters)\nPreview: {preview}",
            "result": content
        }

    @staticmethod
    def write_file(state: AgentState, filename: str, content: str, **kwargs) -> Dict[str, Any]:
        """Create or overwrite a file with the given content"""
        if "files" not in state:
            state["files"] = {}

        state["files"][filename] = content
        return {
            "success": True,
            "summary": f"Successfully wrote/updated file '{filename}' ({len(content)} chars)"
        }

    @staticmethod
    def append_file(state: AgentState, filename: str, content: str, **kwargs) -> Dict[str, Any]:
        """Append text to an existing file (creates if doesn't exist)"""
        if "files" not in state:
            state["files"] = {}

        current = state["files"].get(filename, "")
        new_content = current + ("\n" if current else "") + content
        state["files"][filename] = new_content

        return {
            "success": True,
            "summary": f"Appended {len(content)} chars to '{filename}' (new size: {len(new_content)})"
        }

    # ──────────────────────────────────────────────────────────────────────────────
    #  Todo Management Tools
    # ──────────────────────────────────────────────────────────────────────────────

    @staticmethod
    def create_todo(
        state: AgentState,
        title: str,
        description: str = "",
        priority: str = "medium",
        due_date: str = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Create a single todo item"""
        if "todos" not in state:
            state["todos"] = []

        todo = {
            "title": title.strip(),
            "description": description.strip(),
            "priority": priority.lower(),
            "completed": False,
            "created": datetime.now().isoformat(),
            "due_date": due_date,
            "dependencies": []
        }

        state["todos"].append(todo)
        return {
            "success": True,
            "summary": f"Created task: {title} (priority: {priority})"
        }

    @staticmethod
    def create_multiple_todos(
        state: AgentState,
        todos_list: List[Dict[str, Any]],
        **kwargs
    ) -> Dict[str, Any]:
        """Bulk create multiple todos from a list of dicts"""
        if "todos" not in state:
            state["todos"] = []

        created_count = 0
        for item in todos_list:
            if not isinstance(item, dict) or "title" not in item:
                continue

            todo = {
                "title": item["title"].strip(),
                "description": item.get("description", "").strip(),
                "priority": item.get("priority", "medium").lower(),
                "completed": False,
                "created": datetime.now().isoformat(),
                "due_date": item.get("due_date"),
                "dependencies": item.get("dependencies", [])
            }
            state["todos"].append(todo)
            created_count += 1

        return {
            "success": created_count > 0,
            "summary": f"Created {created_count} new task(s)"
        }

    @staticmethod
    def complete_todo(
        state: AgentState,
        title_match: str = None,
        todo_id: int = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Mark a todo as completed by title match or index"""
        todos = state.get("todos", [])
        if not todos:
            return {"success": False, "summary": "No tasks exist"}

        found = False
        if todo_id is not None and 0 <= todo_id < len(todos):
            todos[todo_id]["completed"] = True
            title = todos[todo_id]["title"]
            found = True
        elif title_match:
            for todo in todos:
                if title_match.lower() in todo["title"].lower():
                    todo["completed"] = True
                    title = todo["title"]
                    found = True
                    break

        if found:
            return {"success": True, "summary": f"Marked as completed: {title}"}
        return {"success": False, "summary": f"Could not find task matching: {title_match or todo_id}"}

    @staticmethod
    def save_file(state: AgentState, filename: str, content: str, **kwargs) -> Dict[str, Any]:
        """
        Save/overwrite content to a file in the virtual file system.
        Creates the file if it doesn't exist.
        """
        if "files" not in state:
            state["files"] = {}

        # Basic validation & sanitization
        filename = filename.strip()
        if not filename:
            filename = "unnamed_file.txt"
        
        filename = filename.replace("..", "").replace("/", "_").replace("\\", "_")

        state["files"][filename] = content

        return {
            "success": True,
            "summary": f"File '{filename}' saved successfully ({len(content)} characters)",
            "file_count": len(state["files"]),
            "saved_filename": filename
        }

    @staticmethod
    def list_files(state: AgentState, **kwargs) -> Dict[str, Any]:
        """List all files currently stored in the virtual file system"""
        files = state.get("files", {})
        if not files:
            return {
                "success": True,
                "summary": "No files exist yet",
                "files": []
            }

        file_list = [
            {"name": name, "size_chars": len(content)}
            for name, content in sorted(files.items())
        ]

        return {
            "success": True,
            "summary": f"Found {len(files)} file(s)",
            "files": file_list
        }

    @staticmethod
    def read_file(state: AgentState, filename: str, **kwargs) -> Dict[str, Any]:
        """Read the content of a saved file"""
        files = state.get("files", {})
        if filename not in files:
            return {
                "success": False,
                "summary": f"File '{filename}' not found",
                "content": None
            }

        content = files[filename]
        preview = content[:200] + "..." if len(content) > 200 else content

        return {
            "success": True,
            "summary": f"Read '{filename}' ({len(content)} chars)",
            "content": content,
            "preview": preview
        }
    # ──────────────────────────────────────────────────────────────────────────────
    #  Advanced / Planning Tools
    # ──────────────────────────────────────────────────────────────────────────────

    @staticmethod
    def create_todos_from_plan(
        state: AgentState,
        plan_json: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Parse structured JSON plan and create todos with dependencies"""
        try:
            plan = json.loads(plan_json)
            todos_created = []

            for phase in plan.get("phases", []):
                phase_name = phase.get("name", "Unnamed phase")
                for task in phase.get("tasks", []):
                    todo = {
                        "title": task.get("title", "").strip(),
                        "description": f"{task.get('description', '')}\n(Phase: {phase_name})",
                        "priority": task.get("priority", "medium").lower(),
                        "dependencies": task.get("dependencies", []),
                        "estimated_time": task.get("estimated_time"),
                        "completed": False,
                        "created": datetime.now().isoformat()
                    }
                    if todo["title"]:
                        state["todos"] = state.get("todos", []) + [todo]
                        todos_created.append(todo["title"])

            count = len(todos_created)
            if count == 0:
                return {"success": False, "summary": "No valid tasks found in plan"}

            return {
                "success": True,
                "summary": f"Created {count} tasks from plan:\n" + "\n".join(f"• {t}" for t in todos_created[:5])
            }

        except json.JSONDecodeError:
            return {"success": False, "summary": "Invalid JSON plan format"}
        except Exception as e:
            return {"success": False, "summary": f"Error processing plan: {str(e)}"}
        

    @staticmethod
    def save_file(state: AgentState, filename: str, content: str, **kwargs) -> Dict[str, Any]:
        """
        Save/overwrite content to a file in the virtual file system.
        Creates the file if it doesn't exist.
        """
        if "files" not in state:
            state["files"] = {}

        # Basic validation & sanitization
        filename = filename.strip()
        if not filename:
            filename = "unnamed_file.txt"
        
        # Optional: prevent path traversal (very basic)
        filename = filename.replace("..", "").replace("/", "_").replace("\\", "_")

        state["files"][filename] = content

        return {
            "success": True,
            "summary": f"File '{filename}' saved successfully ({len(content)} characters)",
            "file_count": len(state["files"]),
            "saved_filename": filename
        }

    @staticmethod
    def list_files(state: AgentState, **kwargs) -> Dict[str, Any]:
        """List all files currently stored in the virtual file system"""
        files = state.get("files", {})
        if not files:
            return {
                "success": True,
                "summary": "No files exist yet",
                "files": []
            }

        file_list = [
            {"name": name, "size_chars": len(content)}
            for name, content in sorted(files.items())
        ]

        return {
            "success": True,
            "summary": f"Found {len(files)} file(s)",
            "files": file_list
        }

    @staticmethod
    def read_file(state: AgentState, filename: str, **kwargs) -> Dict[str, Any]:
        """Read the content of a saved file"""
        files = state.get("files", {})
        if filename not in files:
            return {
                "success": False,
                "summary": f"File '{filename}' not found",
                "content": None
            }

        content = files[filename]
        preview = content[:200] + "..." if len(content) > 200 else content

        return {
            "success": True,
            "summary": f"Read '{filename}' ({len(content)} chars)",
            "content": content,
            "preview": preview
        }   
    @staticmethod
    def create_calendar_event(
        state: AgentState,
        title: str,
        date: str,
        time: str = "09:00",
        duration_hours: float = 1.0,
        description: str = "",
        location: str = "",
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create a calendar event.
        - date: YYYY-MM-DD (or relative like "tomorrow")
        - time: HH:MM (24-hour format)
        """
        if "calendar" not in state:
            state["calendar"] = []

        # Use your existing date/time parsers if available
        from backend.app.utils import parse_relative_date, parse_time

        parsed_date = parse_relative_date(date)
        if not parsed_date:
            parsed_date = date  

        parsed_time = parse_time(time)

        event = {
            "title": title.strip(),
            "date": parsed_date,
            "time": parsed_time,
            "end_time": "",  
            "duration_hours": duration_hours,
            "description": description.strip(),
            "location": location.strip(),
            "created": datetime.now().isoformat(),
            "status": "planned"
        }

        state["calendar"].append(event)

        return {
            "success": True,
            "summary": f"Event created: '{title}' on {parsed_date} at {parsed_time}",
            "event": event,
            "total_events": len(state["calendar"])
        }

    @staticmethod
    def list_calendar_events(
        state: AgentState,
        days_ahead: int = 7,
        **kwargs
    ) -> Dict[str, Any]:
        """List upcoming calendar events (next X days)"""
        from backend.app.utils import get_upcoming_events  # if you have it

        events = state.get("calendar", [])
        if not events:
            return {
                "success": True,
                "summary": "No calendar events yet",
                "events": []
            }

        # Sort by date/time
        sorted_events = sorted(events, key=lambda e: (e.get("date", "9999-99-99"), e.get("time", "00:00")))

        upcoming = []
        today = datetime.now()
        for event in sorted_events:
            try:
                event_date = datetime.strptime(event["date"], "%Y-%m-%d")
                days_until = (event_date - today).days
                if 0 <= days_until <= days_ahead:
                    upcoming.append(event)
            except:
                continue

        return {
            "success": True,
            "summary": f"Found {len(upcoming)} upcoming event(s) in next {days_ahead} days",
            "events": upcoming
        }

    @staticmethod
    def delete_calendar_event(
        state: AgentState,
        title_match: str = None,
        event_id: int = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Delete a calendar event by title match or index"""
        events = state.get("calendar", [])
        if not events:
            return {"success": False, "summary": "No events to delete"}

        deleted = False
        deleted_title = ""

        if event_id is not None and 0 <= event_id < len(events):
            deleted_title = events.pop(event_id)["title"]
            deleted = True

        elif title_match:
            title_match = title_match.lower()
            for i, event in enumerate(events):
                if title_match in event.get("title", "").lower():
                    deleted_title = events.pop(i)["title"]
                    deleted = True
                    break

        if deleted:
            return {
                "success": True,
                "summary": f"Deleted event: '{deleted_title}'",
                "remaining_events": len(events)
            }
        return {
            "success": False,
            "summary": f"No matching event found for '{title_match or event_id}'"
        }


# For easier discovery / documentation
AVAILABLE_TOOLS = {
    name: func.__doc__.strip().split("\n")[0]
    for name, func in ToolExecutor.__dict__.items()
    if callable(func) and not name.startswith("_")
}