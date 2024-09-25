from git import TYPE_CHECKING

from langflow.code_gen.component import generate_script

if TYPE_CHECKING:
    from langflow.graph.graph.base import Graph


def generate_script_from_graph(graph: "Graph"):
    script = generate_script(entry=graph.entry, exit=graph.exit, instances=graph.sort_components())
    return script
