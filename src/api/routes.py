"""
FastAPI route handlers and in-memory session manager for /query and /health endpoints.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.agent.state import create_initial_state
from src.agent.graph import agent_graph
from src.mcp_client import default_mcp_client


router = APIRouter()


class SessionStateManager:
    """Tracks multi-turn conversation history in memory keyed by session_id."""

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


class QueryRequest(BaseModel):
    session_id: str = Field(default="default-session")
    query: str = Field(..., min_length=1)


class QueryResponse(BaseModel):
    status: str
    session_id: str
    clarification_needed: bool = False
    clarification_question: Optional[str] = None
    answer: Optional[str] = None
    sql_queries: Dict[str, str] = Field(default_factory=dict)
    data: Optional[List[Dict[str, Any]]] = None
    visualization: Optional[Dict[str, Any]] = None


@router.get("/health")
def health_check() -> Dict[str, Any]:
    sources = default_mcp_client.list_data_sources()
    return {
        "status": "healthy",
        "service": "Multi-Source Agentic Text-to-SQL with MCP",
        "mcp_sources_count": len(sources),
        "mcp_sources": [s.get("id") for s in sources],
    }


@router.post("/query", response_model=QueryResponse)
def execute_query(payload: QueryRequest) -> QueryResponse:
    session_id = payload.session_id
    user_query = payload.query.strip()

    messages = session_manager.append_message(session_id, "user", user_query)
    initial_state = create_initial_state(
        user_query=user_query,
        session_id=session_id,
        messages=messages,
    )

    final_state = agent_graph.invoke(initial_state)

    if final_state.get("clarification_needed"):
        question = final_state.get("clarification_question") or "Could you clarify your request?"
        session_manager.append_message(session_id, "assistant", question)
        session_manager.update_session_state(session_id, final_state, "clarification_needed")
        return QueryResponse(
            status="clarification_needed",
            session_id=session_id,
            clarification_needed=True,
            clarification_question=question,
        )

    answer = final_state.get("final_answer") or "Query completed."
    session_manager.append_message(session_id, "assistant", answer)
    session_manager.update_session_state(session_id, final_state, "completed")
    session_manager.clear_session(session_id)

    return QueryResponse(
        status="completed",
        session_id=session_id,
        clarification_needed=False,
        clarification_question=None,
        answer=answer,
        sql_queries=final_state.get("generated_sql") or {},
        data=final_state.get("aggregated_data") or [],
        visualization=final_state.get("visualization_config"),
    )
