"""
In-memory session state manager for multi-turn conversational query interactions.
"""

from typing import Any, Dict, List


class SessionStateManager:
    """Manages conversation history and turn status in memory keyed by session_id."""

    def __init__(self):
        self._sessions: Dict[str, Dict[str, Any]] = {}

    def get_session(self, session_id: str) -> Dict[str, Any]:
        if session_id not in self._sessions:
            self._sessions[session_id] = {
                "session_id": session_id,
                "messages": [],
                "status": "initialized",
                "last_state": None,
            }
        return self._sessions[session_id]

    def append_message(self, session_id: str, role: str, content: str) -> List[Dict[str, str]]:
        session = self.get_session(session_id)
        session["messages"].append({"role": role, "content": content})
        return list(session["messages"])

    def update_session_state(self, session_id: str, final_state: Dict[str, Any], status: str) -> None:
        session = self.get_session(session_id)
        session["status"] = status
        session["last_state"] = final_state

    def clear_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)


session_manager = SessionStateManager()
