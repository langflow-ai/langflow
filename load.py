from langflow.load import run_flow_from_json
TWEAKS = {
  }

result = run_flow_from_json(flow="src/backend/base/langflow/initial_setup/starter_projects/Memory Chatbot.json",
                            input_value="message",
                            fallback_to_env_vars=True, # False by default
                            tweaks=TWEAKS)