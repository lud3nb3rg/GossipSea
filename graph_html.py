import json
import os

_TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "templates", "graph_template.html")
_PLACEHOLDER = "__GRAPH_DATA_JSON__"


def render_html(graph_data: dict) -> str:
    with open(_TEMPLATE_PATH, "r", encoding="utf-8") as f:
        template = f.read()
    return template.replace(_PLACEHOLDER, json.dumps(graph_data))


def export_html(graph, path: str) -> None:
    html = render_html(graph.to_graph_data())
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
