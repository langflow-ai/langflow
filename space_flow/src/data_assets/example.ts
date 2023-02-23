export const example = {
    "nodes": [
        {
            "width": 384,
            "height": 271,
            "id": "dndnode_}5",
            "type": "genericNode",
            "position": {
                "x": -640.9237482084102,
                "y": 117.60473769101873
            },
            "data": {
                "type": "ConversationBufferMemory",
                "node": {
                    "template": {
                        "_type": "conversation_buffer",
                        "human_prefix": {
                            "type": "str",
                            "required": false,
                            "placeholder": "",
                            "list": false,
                            "show": false,
                            "multline": false,
                            "value": "Human"
                        },
                        "ai_prefix": {
                            "type": "str",
                            "required": false,
                            "placeholder": "",
                            "list": false,
                            "show": false,
                            "multline": false,
                            "value": "AI"
                        },
                        "buffer": {
                            "type": "str",
                            "required": false,
                            "placeholder": "",
                            "list": false,
                            "show": false,
                            "multline": false,
                            "value": ""
                        },
                        "output_key": {
                            "type": "str",
                            "required": false,
                            "placeholder": "",
                            "list": false,
                            "show": false,
                            "multline": false,
                            "value": null
                        },
                        "input_key": {
                            "type": "str",
                            "required": false,
                            "placeholder": "",
                            "list": false,
                            "show": false,
                            "multline": false,
                            "value": null
                        },
                        "memory_key": {
                            "type": "str",
                            "required": false,
                            "placeholder": "",
                            "list": false,
                            "show": false,
                            "multline": false,
                            "value": "history"
                        }
                    },
                    "description": "Buffer for storing conversation memory.",
                    "base_classes": [
                        "Memory"
                    ]
                },
                "id": "dndnode_}5",
                "value": null
            },
            "selected": false,
            "positionAbsolute": {
                "x": -640.9237482084102,
                "y": 117.60473769101873
            },
            "dragging": false
        },
        {
            "width": 384,
            "height": 447,
            "id": "dndnode_}7",
            "type": "genericNode",
            "position": {
                "x": -86,
                "y": 522
            },
            "data": {
                "type": "LLMChain",
                "node": {
                    "template": {
                        "_type": "llm_chain",
                        "memory": {
                            "type": "Memory",
                            "required": false,
                            "placeholder": "",
                            "list": false,
                            "show": true,
                            "multline": false,
                            "value": null
                        },
                        "verbose": {
                            "type": "bool",
                            "required": false,
                            "placeholder": "",
                            "list": false,
                            "show": true,
                            "multline": false,
                            "value": false
                        },
                        "prompt": {
                            "type": "BasePromptTemplate",
                            "required": true,
                            "placeholder": "",
                            "list": false,
                            "show": true,
                            "multline": false
                        },
                        "llm": {
                            "type": "BaseLLM",
                            "required": true,
                            "placeholder": "",
                            "list": false,
                            "show": true,
                            "multline": false
                        },
                        "output_key": {
                            "type": "str",
                            "required": false,
                            "placeholder": "",
                            "list": false,
                            "show": false,
                            "multline": false,
                            "value": "text"
                        }
                    },
                    "description": "Chain to run queries against LLMs.",
                    "base_classes": [
                        "Chain"
                    ]
                },
                "id": "dndnode_}7",
                "value": null
            },
            "selected": false,
            "positionAbsolute": {
                "x": -86,
                "y": 522
            },
            "dragging": false
        },
        {
            "width": 384,
            "height": 357,
            "id": "dndnode_}8",
            "type": "genericNode",
            "position": {
                "x": -633.4,
                "y": 230
            },
            "data": {
                "type": "PromptTemplate",
                "node": {
                    "template": {
                        "_type": "prompt",
                        "input_variables": {
                            "type": "str",
                            "required": true,
                            "placeholder": "",
                            "list": true,
                            "show": false,
                            "multline": false
                        },
                        "output_parser": {
                            "type": "BaseOutputParser",
                            "required": false,
                            "placeholder": "",
                            "list": false,
                            "show": false,
                            "multline": false,
                            "value": null
                        },
                        "template": {
                            "type": "str",
                            "required": true,
                            "placeholder": "",
                            "list": false,
                            "show": true,
                            "multline": true,
                            "value": "aaaaa"
                        },
                        "template_format": {
                            "type": "str",
                            "required": false,
                            "placeholder": "",
                            "list": false,
                            "show": false,
                            "multline": false,
                            "value": "f-string"
                        },
                        "validate_template": {
                            "type": "bool",
                            "required": false,
                            "placeholder": "",
                            "list": false,
                            "show": false,
                            "multline": false,
                            "value": true
                        }
                    },
                    "description": "Schema to represent a prompt for an LLM.",
                    "base_classes": [
                        "BasePromptTemplate"
                    ]
                },
                "id": "dndnode_}8",
                "value": null
            },
            "selected": false,
            "positionAbsolute": {
                "x": -633.4,
                "y": 230
            },
            "dragging": false
        },
        {
            "width": 384,
            "height": 453,
            "id": "dndnode_}9",
            "type": "genericNode",
            "position": {
                "x": -655.1999999999999,
                "y": 615
            },
            "data": {
                "type": "AI21",
                "node": {
                    "template": {
                        "_type": "ai21",
                        "cache": {
                            "type": "bool",
                            "required": false,
                            "placeholder": "",
                            "list": false,
                            "show": false,
                            "multline": false,
                            "value": null
                        },
                        "verbose": {
                            "type": "bool",
                            "required": false,
                            "placeholder": "",
                            "list": false,
                            "show": true,
                            "multline": false,
                            "value": false
                        },
                        "model": {
                            "type": "str",
                            "required": false,
                            "placeholder": "",
                            "list": false,
                            "show": false,
                            "multline": false,
                            "value": "j1-jumbo"
                        },
                        "temperature": {
                            "type": "float",
                            "required": false,
                            "placeholder": "",
                            "list": false,
                            "show": false,
                            "multline": false,
                            "value": 0.7
                        },
                        "maxTokens": {
                            "type": "int",
                            "required": false,
                            "placeholder": "",
                            "list": false,
                            "show": false,
                            "multline": false,
                            "value": 256
                        },
                        "minTokens": {
                            "type": "int",
                            "required": false,
                            "placeholder": "",
                            "list": false,
                            "show": false,
                            "multline": false,
                            "value": 0
                        },
                        "topP": {
                            "type": "float",
                            "required": false,
                            "placeholder": "",
                            "list": false,
                            "show": false,
                            "multline": false,
                            "value": 1
                        },
                        "presencePenalty": {
                            "type": "AI21PenaltyData",
                            "required": false,
                            "placeholder": "",
                            "list": false,
                            "show": false,
                            "multline": false,
                            "value": {
                                "scale": 0,
                                "applyToWhitespaces": true,
                                "applyToPunctuations": true,
                                "applyToNumbers": true,
                                "applyToStopwords": true,
                                "applyToEmojis": true
                            }
                        },
                        "countPenalty": {
                            "type": "AI21PenaltyData",
                            "required": false,
                            "placeholder": "",
                            "list": false,
                            "show": false,
                            "multline": false,
                            "value": {
                                "scale": 0,
                                "applyToWhitespaces": true,
                                "applyToPunctuations": true,
                                "applyToNumbers": true,
                                "applyToStopwords": true,
                                "applyToEmojis": true
                            }
                        },
                        "frequencyPenalty": {
                            "type": "AI21PenaltyData",
                            "required": false,
                            "placeholder": "",
                            "list": false,
                            "show": false,
                            "multline": false,
                            "value": {
                                "scale": 0,
                                "applyToWhitespaces": true,
                                "applyToPunctuations": true,
                                "applyToNumbers": true,
                                "applyToStopwords": true,
                                "applyToEmojis": true
                            }
                        },
                        "numResults": {
                            "type": "int",
                            "required": false,
                            "placeholder": "",
                            "list": false,
                            "show": false,
                            "multline": false,
                            "value": 1
                        },
                        "logitBias": {
                            "type": "dict[str, float]",
                            "required": false,
                            "placeholder": "",
                            "list": false,
                            "show": false,
                            "multline": false,
                            "value": null
                        },
                        "ai21_api_key": {
                            "type": "str",
                            "required": false,
                            "placeholder": "",
                            "list": false,
                            "show": true,
                            "multline": false,
                            "value": "aaaa"
                        },
                        "base_url": {
                            "type": "str",
                            "required": false,
                            "placeholder": "",
                            "list": false,
                            "show": false,
                            "multline": false,
                            "value": null
                        }
                    },
                    "description": "Wrapper around AI21 large language models.To use, you should have the environment variable ``AI21_API_KEY``set with your API key.",
                    "base_classes": [
                        "LLM",
                        "BaseLLM"
                    ]
                },
                "id": "dndnode_}9",
                "value": null
            },
            "selected": false,
            "positionAbsolute": {
                "x": -655.1999999999999,
                "y": 615
            },
            "dragging": false
        },
        {
            "width": 384,
            "height": 351,
            "id": "dndnode_}11",
            "type": "genericNode",
            "position": {
                "x": 638.4588569554073,
                "y": 325.32407743706693
            },
            "data": {
                "type": "ZeroShotAgent",
                "node": {
                    "template": {
                        "_type": "zero-shot-react-description",
                        "llm_chain": {
                            "type": "LLMChain",
                            "required": true,
                            "placeholder": "",
                            "list": false,
                            "show": true,
                            "multline": false
                        },
                        "allowed_tools": {
                            "type": "Tool",
                            "required": false,
                            "placeholder": "",
                            "list": true,
                            "show": true,
                            "multline": false,
                            "value": null
                        },
                        "return_values": {
                            "type": "str",
                            "required": false,
                            "placeholder": "",
                            "list": true,
                            "show": false,
                            "multline": false,
                            "value": [
                                "output"
                            ]
                        }
                    },
                    "description": "Agent for the MRKL chain.",
                    "base_classes": [
                        "Agent"
                    ]
                },
                "id": "dndnode_}11",
                "value": null
            },
            "positionAbsolute": {
                "x": 638.4588569554073,
                "y": 325.32407743706693
            }
        },
        {
            "width": 384,
            "height": 283,
            "id": "dndnode_}12",
            "type": "genericNode",
            "position": {
                "x": -88.20259321315393,
                "y": 992.0115499525607
            },
            "data": {
                "type": "Requests",
                "node": {
                    "template": {
                        "_type": "requests"
                    },
                    "name": "Requests",
                    "description": "A portal to the internet. Use this when you need to get specific content from a site. Input should be a specific url, and the output will be all the text on that page.",
                    "base_classes": [
                        "Tool"
                    ]
                },
                "id": "dndnode_}12",
                "value": null
            },
            "selected": false,
            "positionAbsolute": {
                "x": -88.20259321315393,
                "y": 992.0115499525607
            },
            "dragging": false
        },
        {
            "width": 155,
            "height": 62,
            "id": "dndnode_}13",
            "type": "chatOutputNode",
            "position": {
                "x": 1187.9878614974666,
                "y": 492.6933173991155
            },
            "data": {
                "type": "chatOutput",
                "id": "dndnode_}13",
                "value": null
            },
            "selected": false,
            "positionAbsolute": {
                "x": 1187.9878614974666,
                "y": 492.6933173991155
            },
            "dragging": false
        },
        {
            "width": 139,
            "height": 62,
            "id": "dndnode_}14",
            "type": "chatInputNode",
            "position": {
                "x": -1098.8338538506573,
                "y": 562.4305007166358
            },
            "data": {
                "type": "chatInput",
                "id": "dndnode_}14",
                "value": null
            },
            "selected": true,
            "positionAbsolute": {
                "x": -1098.8338538506573,
                "y": 562.4305007166358
            },
            "dragging": false
        }
    ],
    "edges": [
        {
            "source": "dndnode_}2",
            "sourceHandle": "PromptTemplate|example_prompt|dndnode_}2",
            "target": "dndnode_}1",
            "targetHandle": "PromptTemplate|dndnode_}1|BasePromptTemplate",
            "className": "animate-pulse",
            "id": "reactflow__edge-dndnode_}2PromptTemplate|example_prompt|dndnode_}2-dndnode_}1PromptTemplate|dndnode_}1|BasePromptTemplate"
        },
        {
            "source": "dndnode_}7",
            "sourceHandle": "BasePromptTemplate|prompt|dndnode_}7",
            "target": "dndnode_}8",
            "targetHandle": "PromptTemplate|dndnode_}8|BasePromptTemplate",
            "className": "animate-pulse",
            "id": "reactflow__edge-dndnode_}7BasePromptTemplate|prompt|dndnode_}7-dndnode_}8PromptTemplate|dndnode_}8|BasePromptTemplate"
        },
        {
            "source": "dndnode_}7",
            "sourceHandle": "BaseLLM|llm|dndnode_}7",
            "target": "dndnode_}9",
            "targetHandle": "AI21|dndnode_}9|LLM,|BaseLLM",
            "className": "animate-pulse",
            "id": "reactflow__edge-dndnode_}7BaseLLM|llm|dndnode_}7-dndnode_}9AI21|dndnode_}9|LLM,|BaseLLM"
        },
        {
            "source": "dndnode_}7",
            "sourceHandle": "Memory|memory|dndnode_}7",
            "target": "dndnode_}5",
            "targetHandle": "ConversationBufferMemory|dndnode_}5|Memory",
            "className": "animate-pulse",
            "id": "reactflow__edge-dndnode_}7Memory|memory|dndnode_}7-dndnode_}5ConversationBufferMemory|dndnode_}5|Memory"
        },
        {
            "source": "dndnode_}11",
            "sourceHandle": "LLMChain|llm_chain|dndnode_}11",
            "target": "dndnode_}7",
            "targetHandle": "LLMChain|dndnode_}7|Chain",
            "className": "animate-pulse",
            "id": "reactflow__edge-dndnode_}11LLMChain|llm_chain|dndnode_}11-dndnode_}7LLMChain|dndnode_}7|Chain"
        },
        {
            "source": "dndnode_}11",
            "sourceHandle": "Tool|allowed_tools|dndnode_}11",
            "target": "dndnode_}12",
            "targetHandle": "Requests|dndnode_}12|Tool",
            "className": "animate-pulse",
            "id": "reactflow__edge-dndnode_}11Tool|allowed_tools|dndnode_}11-dndnode_}12Requests|dndnode_}12|Tool"
        },
        {
            "source": "dndnode_}13",
            "sourceHandle": "str|output|dndnode_}13",
            "target": "dndnode_}11",
            "targetHandle": "ZeroShotAgent|dndnode_}11|Agent",
            "className": "animate-pulse",
            "id": "reactflow__edge-dndnode_}13str|output|dndnode_}13-dndnode_}11ZeroShotAgent|dndnode_}11|Agent",
            "selected": false
        }
    ],
    "viewport": {
        "x": 765.8392857133035,
        "y": -83.25008407339476,
        "zoom": 0.7169776240079136
    }
}