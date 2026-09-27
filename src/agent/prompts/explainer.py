"""
Prompt templates for the Result Explainer node.
"""

EXPLAINER_SYSTEM_PROMPT = """You are an executive data analyst synthesizing cross-source query results into a concise, accurate business summary.
Provide:
1. "final_answer": A natural-language summary directly answering the user's question with key figures.
2. "visualization_config": A chart configuration object (chart_type, title, x_axis, y_axes).
"""


def format_explainer_prompt(user_query: str, aggregated_data: list) -> str:
    return (
        f"User Question: {user_query}\n"
        f"Aggregated Cross-Source Data: {aggregated_data}\n"
        "Synthesize the business answer and visualization configuration in JSON."
    )
