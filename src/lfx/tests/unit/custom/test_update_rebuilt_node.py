import copy
import inspect
import json
from pathlib import Path

from lfx.components.models_and_agents.prompt import PromptComponent
from lfx.custom.custom_component.component import Component
from lfx.custom.utils import build_custom_component_template, update_rebuilt_node

SEO_V1_11_6 = Path(__file__).parents[2] / "fixtures" / "starter_flows" / "v1.11.6" / "seo_keyword_generator.json"


async def test_update_rebuilt_node_keeps_saved_prompt_variables() -> None:
    flow = json.loads(SEO_V1_11_6.read_text(encoding="utf-8"))
    saved = next(node for node in flow["data"]["nodes"] if node["data"]["type"] == "Prompt")["data"]["node"]
    variables = saved["custom_fields"]["template"]
    assert variables
    assert all(saved["template"][name]["value"] for name in variables)
    code = Path(inspect.getsourcefile(PromptComponent)).read_text(encoding="utf-8")
    built, component = build_custom_component_template(Component(_code=code))
    assert not set(variables) & set(built["template"])

    updated = await update_rebuilt_node(component, built, copy.deepcopy(saved))

    assert {name: updated["template"][name]["value"] for name in variables} == {
        name: saved["template"][name]["value"] for name in variables
    }
