from langchain.agents.mrkl import prompt


def get_custom_prompts():
    """Get custom prompts."""

    return {
        "ZeroShotPrompt": {
            "template": {
                "_type": "zero_shot",
                "prefix": {
                    "type": "str",
                    "required": False,
                    "placeholder": "",
                    "list": False,
                    "show": True,
                    "multiline": True,
                    "value": prompt.PREFIX,
                },
                "suffix": {
                    "type": "str",
                    "required": True,
                    "placeholder": "",
                    "list": False,
                    "show": True,
                    "multiline": True,
                    "value": prompt.SUFFIX,
                },
                "format_instructions": {
                    "type": "str",
                    "required": False,
                    "placeholder": "",
                    "list": False,
                    "show": True,
                    "multiline": True,
                    "value": prompt.FORMAT_INSTRUCTIONS,
                },
            },
            "description": "Prompt template for Zero Shot Agent.",
            "base_classes": ["BasePromptTemplate"],
        }
    }
