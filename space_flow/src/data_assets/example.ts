export const example = {
    "nodes": [
        {
            "width": 384,
            "height": 413,
            "id": "dndnode_1",
            "type": "genericNode",
            "position": {
                "x": 124.66903342355295,
                "y": -20.27227649302739
            },
            "data": {
                "type": "OpenAI",
                "node": {
                    "template": {
                        "_type": "openai",
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
                            "value": null
                        },
                        "client": {
                            "type": "Any",
                            "required": false,
                            "placeholder": "",
                            "list": false,
                            "show": false,
                            "multline": false,
                            "value": null
                        },
                        "model_name": {
                            "type": "str",
                            "required": false,
                            "placeholder": "",
                            "list": false,
                            "show": false,
                            "multline": false,
                            "value": "text-davinci-003"
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
                        "max_tokens": {
                            "type": "int",
                            "required": false,
                            "placeholder": "",
                            "list": false,
                            "show": false,
                            "multline": false,
                            "value": 256
                        },
                        "top_p": {
                            "type": "float",
                            "required": false,
                            "placeholder": "",
                            "list": false,
                            "show": false,
                            "multline": false,
                            "value": 1
                        },
                        "frequency_penalty": {
                            "type": "float",
                            "required": false,
                            "placeholder": "",
                            "list": false,
                            "show": false,
                            "multline": false,
                            "value": 0
                        },
                        "presence_penalty": {
                            "type": "float",
                            "required": false,
                            "placeholder": "",
                            "list": false,
                            "show": false,
                            "multline": false,
                            "value": 0
                        },
                        "n": {
                            "type": "int",
                            "required": false,
                            "placeholder": "",
                            "list": false,
                            "show": false,
                            "multline": false,
                            "value": 1
                        },
                        "best_of": {
                            "type": "int",
                            "required": false,
                            "placeholder": "",
                            "list": false,
                            "show": false,
                            "multline": false,
                            "value": 1
                        },
                        "model_kwargs": {
                            "type": "dict[str, Any]",
                            "required": false,
                            "placeholder": "",
                            "list": false,
                            "show": false,
                            "multline": false,
                            "value": null
                        },
                        "openai_api_key": {
                            "type": "str",
                            "required": false,
                            "placeholder": "",
                            "list": false,
                            "show": true,
                            "multline": false,
                            "value": "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"
                        },
                        "batch_size": {
                            "type": "int",
                            "required": false,
                            "placeholder": "",
                            "list": false,
                            "show": false,
                            "multline": false,
                            "value": 20
                        },
                        "request_timeout": {
                            "type": "Union[float, Tuple[float, float], NoneType]",
                            "required": false,
                            "placeholder": "",
                            "list": false,
                            "show": false,
                            "multline": false,
                            "value": null
                        },
                        "logit_bias": {
                            "type": "dict[str, float]",
                            "required": false,
                            "placeholder": "",
                            "list": false,
                            "show": false,
                            "multline": false,
                            "value": null
                        },
                        "max_retries": {
                            "type": "int",
                            "required": false,
                            "placeholder": "",
                            "list": false,
                            "show": false,
                            "multline": false,
                            "value": 6
                        }
                    },
                    "description": "Generic OpenAI class that uses model name.",
                    "base_classes": [
                        "BaseOpenAI",
                        "BaseLLM"
                    ]
                },
                "id": "dndnode_1",
                "value": null,
                "reactFlowInstance": {
                    "viewportInitialized": true
                }
            },
            "selected": false,
            "positionAbsolute": {
                "x": 124.66903342355295,
                "y": -20.27227649302739
            },
            "dragging": false
        },
        {
            "width": 152,
            "height": 62,
            "id": "dndnode_2",
            "type": "chatOutputNode",
            "position": {
                "x": 688.2448440290276,
                "y": 315.1849334347801
            },
            "data": {
                "type": "chatOutput",
                "id": "dndnode_2",
                "value": null,
                "reactFlowInstance": {
                    "viewportInitialized": true
                }
            },
            "selected": false,
            "positionAbsolute": {
                "x": 688.2448440290276,
                "y": 315.1849334347801
            },
            "dragging": false
        }
    ],
    "edges": [
        {
            "source": "dndnode_1",
            "sourceHandle": "OpenAI|dndnode_1|BaseOpenAI,|BaseLLM",
            "target": "dndnode_2",
            "targetHandle": "str|output|dndnode_2",
            "className": "animate-pulse",
            "id": "reactflow__edge-dndnode_1OpenAI|dndnode_1|BaseOpenAI,|BaseLLM-dndnode_2str|output|dndnode_2"
        }
    ],
    "viewport": {
        "x": 283.7086041469587,
        "y": 207.97093260601437,
        "zoom": 0.5937798330367052
    },
    "message": "Tell me a joke."
}