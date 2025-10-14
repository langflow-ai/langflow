"""Component Mapper for Genesis to Langflow components."""

from typing import Dict, Any, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

# Lazy import to avoid circular dependencies
_component_schema_inspector = None


class ComponentMapper:
    """Maps Genesis specification types to AI Studio (Langflow) components."""

    def __init__(self):
        """Initialize component mapper with mappings."""
        self._init_mappings()
        self._use_real_introspection = True  # Flag to enable real component inspection

    def _init_mappings(self):
        """Initialize all component mappings."""
        # AutonomizeModel variants - all clinical models unified
        self.AUTONOMIZE_MODELS = {
            "genesis:autonomize_model": {
                "component": "AutonomizeModel",
                "config": {"selected_model": "Clinical LLM"}  # Default model
            },
            "genesis:rxnorm": {
                "component": "AutonomizeModel",
                "config": {"selected_model": "RxNorm Code"}
            },
            "genesis:icd10": {
                "component": "AutonomizeModel",
                "config": {"selected_model": "ICD-10 Code"}
            },
            "genesis:cpt_code": {
                "component": "AutonomizeModel",
                "config": {"selected_model": "CPT Code"}
            },
            "genesis:cpt": {  # Alias
                "component": "AutonomizeModel",
                "config": {"selected_model": "CPT Code"}
            },
            "genesis:clinical_llm": {
                "component": "AutonomizeModel",
                "config": {"selected_model": "Clinical LLM"}
            },
            "genesis:clinical_note_classifier": {
                "component": "AutonomizeModel",
                "config": {"selected_model": "Clinical Note Classifier"}
            },
            "genesis:combined_entity_linking": {
                "component": "AutonomizeModel",
                "config": {"selected_model": "Combined Entity Linking"}
            }
        }

        # MCP components
        self.MCP_MAPPINGS = {
            "genesis:mcp_tool": {
                "component": "MCPTools",
                "config": {
                    # For backward compatibility with existing tool_name-only configurations
                    # Provide a default command that enables STDIO mode detection
                    "command": "echo '{\"tools\": [], \"capabilities\": {}}'",  # Default JSON response for compatibility
                    "args": [],
                    "env": {},
                    "url": "",
                    "headers": {},
                    "timeout_seconds": 30,
                    "sse_read_timeout_seconds": 30
                },
                "dataType": "MCPTools"
            },
            "genesis:mcp_sse_tool": {
                "component": "MCPTools",
                "config": {
                    "connection_mode": "SSE",
                    "url": "",
                    "headers": {},
                    "timeout_seconds": 30,
                    "sse_read_timeout_seconds": 30
                },
                "dataType": "MCPTools"
            },
            "genesis:mcp_stdio_tool": {
                "component": "MCPTools",
                "config": {
                    "connection_mode": "Stdio",
                    "command": "",
                    "args": [],
                    "env": {}
                },
                "dataType": "MCPTools"
            },
            "genesis:mcp_client": {
                "component": "MCPClient",
                "config": {}
            },
            "genesis:mcp_server": {
                "component": "MCPServer",
                "config": {}
            }
        }

        # Standard component mappings
        self.STANDARD_MAPPINGS = {
            # Agents and Language Models
            "genesis:agent": {"component": "Agent", "config": {}},
            "genesis:autonomize_agent": {"component": "Agent", "config": {}},  # Map to Agent since AutonomizeAgent may not exist
            "genesis:language_model": {"component": "Agent", "config": {}},  # Map to Agent as it has LLM capabilities

            # Input/Output Components
            "genesis:chat_input": {"component": "ChatInput", "config": {}},
            "genesis:chat_output": {"component": "ChatOutput", "config": {}},
            "genesis:text_input": {"component": "TextInput", "config": {}},
            "genesis:text_output": {"component": "TextOutput", "config": {}},
            "genesis:json_input": {"component": "CreateData", "config": {}},  # Map to existing CreateData
            "genesis:json_output": {"component": "ParseData", "config": {}},
            "genesis:file_input": {"component": "File", "config": {}},  # Map to File component
            "genesis:file": {"component": "File", "config": {}},
            "genesis:directory": {"component": "Directory", "config": {}},
            "genesis:url": {"component": "URL", "config": {}},
            "genesis:file_path": {"component": "FilePathComponent", "config": {}},
            "genesis:blob_storage": {"component": "BlobStorageComponent", "config": {}},

            # Prompts
            "genesis:prompt": {"component": "PromptComponent", "config": {}},
            "genesis:prompt_template": {"component": "PromptComponent", "config": {}, "dataType": "PromptComponent"},  # Use existing PromptComponent
            "genesis:genesis_prompt": {"component": "GenesisPromptComponent", "config": {}, "dataType": "PromptComponent"},

            # Memory
            "genesis:memory": {"component": "Memory", "config": {}},
            "genesis:conversation_memory": {"component": "ConversationChain", "config": {}},
            "genesis:conversation_chain": {"component": "ConversationChain", "config": {}},

            # Tools - Infrastructure components (keep) + MCP fallbacks for domain-specific ones
            "genesis:knowledge_hub_search": {"component": "KnowledgeHubSearch", "config": {}, "dataType": "KnowledgeHubSearch"},
            "genesis:calculator": {"component": "Calculator", "config": {}},

            # API Components - Native HTTP request support with secure header handling
            # Note: Headers support sensitive data like API keys, auth tokens, etc.
            # Use environment variables or secure configuration for sensitive headers
            "genesis:api_request": {
                "component": "APIRequest",
                "config": {
                    "timeout": 30,
                    "follow_redirects": True,
                    "headers": [{"key": "Content-Type", "value": "application/json"}]
                },
                "dataType": "Data"
            },
            "genesis:http_request": {
                "component": "APIRequest",
                "config": {
                    "timeout": 30,
                    "follow_redirects": True,
                    "headers": [{"key": "Content-Type", "value": "application/json"}]
                },
                "dataType": "Data"
            },

            # Domain-specific tools -> MCP Tools Component (simplified approach)
            "genesis:encoder_pro": {"component": "MCPTools", "config": {"tool_name": "encoder_pro", "description": "Medical coding and validation tool"}, "dataType": "MCPTools"},
            "genesis:pa_lookup": {"component": "MCPTools", "config": {"tool_name": "pa_lookup", "description": "Prior authorization lookup tool"}, "dataType": "MCPTools"},
            "genesis:eligibility_component": {"component": "MCPTools", "config": {"tool_name": "eligibility_check", "description": "Member eligibility validation tool"}, "dataType": "MCPTools"},
            "genesis:qnext_auth_history": {"component": "MCPTools", "config": {"tool_name": "qnext_auth_history", "description": "QNext authorization history tool"}, "dataType": "MCPTools"},
            "genesis:api_component": {"component": "MCPTools", "config": {"tool_name": "api_component", "description": "Generic API integration tool"}, "dataType": "MCPTools"},
            # Document Processing Components
            "genesis:form_recognizer": {"component": "AzureDocumentIntelligenceComponent", "config": {}, "dataType": "AzureDocumentIntelligenceComponent"},
            "genesis:document_intelligence": {"component": "AzureDocumentIntelligenceComponent", "config": {}, "dataType": "AzureDocumentIntelligenceComponent"},
            "genesis:docling_inline": {"component": "DoclingInlineComponent", "config": {}},
            "genesis:docling_remote": {"component": "DoclingRemoteComponent", "config": {}},
            "genesis:chunk_docling": {"component": "ChunkDoclingDocumentComponent", "config": {}},
            "genesis:export_docling": {"component": "ExportDoclingDocumentComponent", "config": {}},

            # Data Processing Components
            "genesis:data_transformer": {"component": "MCPTools", "config": {"tool_name": "data_transformer", "description": "Data transformation and standardization tool"}, "dataType": "MCPTools"},
            "genesis:csv_to_data": {"component": "CSVToDataComponent", "config": {}},
            "genesis:json_to_data": {"component": "JSONToDataComponent", "config": {}},
            "genesis:parse_data": {"component": "ParseData", "config": {}},
            "genesis:filter_data": {"component": "FilterData", "config": {}},
            "genesis:merge_data": {"component": "MergeData", "config": {}},
            "genesis:create_data": {"component": "CreateData", "config": {}},
            "genesis:update_data": {"component": "UpdateData", "config": {}},
            "genesis:select_data": {"component": "SelectData", "config": {}},

            # Text Processing Components
            "genesis:split_text": {"component": "SplitText", "config": {}},
            "genesis:combine_text": {"component": "CombineText", "config": {}},
            "genesis:regex": {"component": "RegexComponent", "config": {}},
            "genesis:text_embedder": {"component": "TextEmbedder", "config": {}},

            # Vector stores and Databases
            "genesis:vector_store": {"component": "QdrantVectorStore", "config": {}},
            "genesis:qdrant": {"component": "QdrantVectorStore", "config": {}},
            "genesis:faiss": {"component": "FAISS", "config": {}},
            "genesis:chroma": {"component": "Chroma", "config": {}},
            "genesis:cassandra": {"component": "Cassandra", "config": {}},
            "genesis:couchbase": {"component": "Couchbase", "config": {}},

            # LLMs
            "genesis:openai": {"component": "OpenAIModel", "config": {}},
            "genesis:azure_openai": {"component": "AzureOpenAIModel", "config": {}},
            "genesis:anthropic": {"component": "AnthropicModel", "config": {}},

            # CrewAI
            "genesis:crewai_agent": {"component": "CrewAIAgentComponent", "config": {}},
            "genesis:crewai_sequential_task": {"component": "CrewAIAgentComponent", "config": {"task_type": "sequential"}},
            "genesis:crewai_sequential_crew": {"component": "CrewAIAgentComponent", "config": {"crew_type": "sequential"}},
            "genesis:crewai_hierarchical_crew": {"component": "CrewAIAgentComponent", "config": {"crew_type": "hierarchical"}},

            # Web Search and External Data
            "genesis:web_search": {"component": "WebSearchComponent", "config": {}},
            "genesis:news_search": {"component": "NewsSearchComponent", "config": {}},
            "genesis:wikipedia": {"component": "WikipediaComponent", "config": {}},
            "genesis:arxiv": {"component": "ArxivComponent", "config": {}},
            "genesis:bing_search": {"component": "BingSearchComponent", "config": {}},
            "genesis:rss": {"component": "RSSComponent", "config": {}},
            "genesis:webhook": {"component": "WebhookComponent", "config": {}},

            # SQL and Databases
            "genesis:sql_executor": {"component": "SQLExecutor", "config": {}},

            # Helper Components
            "genesis:id_generator": {"component": "IDGenerator", "config": {}},
            "genesis:current_date": {"component": "CurrentDate", "config": {}},
            "genesis:create_list": {"component": "CreateList", "config": {}},
            "genesis:store_message": {"component": "StoreMessage", "config": {}},

            # Embedding Components
            "genesis:openai_embeddings": {"component": "OpenAIEmbeddings", "config": {}},
            "genesis:azure_openai_embeddings": {"component": "AzureOpenAIEmbeddings", "config": {}},
            "genesis:cohere_embeddings": {"component": "CohereEmbeddings", "config": {}},

            # Integration Services
            "genesis:notion": {"component": "NotionComponent", "config": {}},
            "genesis:confluence": {"component": "ConfluenceComponent", "config": {}},
            "genesis:google_drive": {"component": "GoogleDriveComponent", "config": {}},
            "genesis:composio": {"component": "ComposioComponent", "config": {}}
        }

    def map_component(self, spec_type: str) -> Dict[str, Any]:
        """
        Map a Genesis specification type to Langflow component.

        Args:
            spec_type: Component type from specification (e.g., "genesis:rxnorm")

        Returns:
            Dictionary with component name and configuration
        """
        # Check AutonomizeModel mappings first
        if spec_type in self.AUTONOMIZE_MODELS:
            return self.AUTONOMIZE_MODELS[spec_type].copy()

        # Check MCP mappings
        if spec_type in self.MCP_MAPPINGS:
            return self.MCP_MAPPINGS[spec_type].copy()

        # Check standard mappings
        if spec_type in self.STANDARD_MAPPINGS:
            return self.STANDARD_MAPPINGS[spec_type].copy()

        # Try to handle unknown types intelligently
        return self._handle_unknown_type(spec_type)

    def _handle_unknown_type(self, spec_type: str) -> Dict[str, Any]:
        """Handle unknown component types with intelligent fallbacks."""
        # Remove genesis: prefix if present
        base_type = spec_type.replace("genesis:", "") if spec_type.startswith("genesis:") else spec_type

        # Pattern-based fallbacks
        if "model" in base_type.lower() or "llm" in base_type.lower():
            # Check if it's a clinical model
            if any(term in base_type.lower() for term in ["clinical", "rxnorm", "icd", "cpt", "medical"]):
                logger.warning(f"Unknown clinical model type '{spec_type}', using AutonomizeModel")
                return {"component": "AutonomizeModel", "config": {}}
            else:
                logger.warning(f"Unknown LLM type '{spec_type}', using OpenAIModel")
                return {"component": "OpenAIModel", "config": {}}

        elif "agent" in base_type.lower():
            logger.warning(f"Unknown agent type '{spec_type}', using Agent")
            return {"component": "Agent", "config": {}}

        elif "tool" in base_type.lower() or "component" in base_type.lower():
            logger.warning(f"Unknown tool/component type '{spec_type}', using MCPTools as fallback")
            return {"component": "MCPTools", "config": {}}

        elif "memory" in base_type.lower():
            logger.warning(f"Unknown memory type '{spec_type}', using Memory")
            return {"component": "Memory", "config": {}}

        elif "prompt" in base_type.lower():
            logger.warning(f"Unknown prompt type '{spec_type}', using Prompt")
            return {"component": "Prompt", "config": {}}

        elif "input" in base_type.lower():
            logger.warning(f"Unknown input type '{spec_type}', using ChatInput")
            return {"component": "ChatInput", "config": {}}

        elif "output" in base_type.lower():
            logger.warning(f"Unknown output type '{spec_type}', using ChatOutput")
            return {"component": "ChatOutput", "config": {}}

        else:
            # Default to MCPTools for complete unknowns - better than CustomComponent
            logger.warning(f"Completely unknown type '{spec_type}', using MCPTools as fallback")
            return {"component": "MCPTools", "config": {}}

    def get_component_io_mapping(self, component_type: str = None) -> Dict[str, Any]:
        """
        Get input/output field mappings for component types.

        Args:
            component_type: Optional specific component type to get mapping for.
                           If None, returns all mappings.

        Returns:
            Dictionary with component I/O mappings (enhanced with real introspection if available)
        """
        # Use enhanced method that includes real component introspection
        all_mappings = self.get_component_io_mapping_enhanced()

        if component_type:
            return all_mappings.get(component_type, {
                "input_field": "input_value",
                "output_field": "output",
                "output_types": ["Any"],
                "input_types": ["any"]
            })

        return all_mappings

    def is_tool_component(self, spec_type: str) -> bool:
        """Check if a component type should be used as a tool."""
        # MCP components are always tools
        if spec_type in self.MCP_MAPPINGS:
            return True

        # Check if it's a known tool type
        tool_types = [
            # Core tools
            "genesis:knowledge_hub_search",
            "genesis:pa_lookup",
            "genesis:eligibility_component",
            "genesis:encoder_pro",
            "genesis:calculator",
            "genesis:api_component",
            "genesis:mcp_tool",
            "genesis:mcp_sse_tool",
            "genesis:mcp_stdio_tool",

            # Web and search tools
            "genesis:web_search",
            "genesis:news_search",
            "genesis:wikipedia",
            "genesis:arxiv",
            "genesis:bing_search",

            # API and integration tools
            "genesis:api_request",
            "genesis:http_request",
            "genesis:webhook",

            # Document processing tools
            "genesis:form_recognizer",
            "genesis:document_intelligence",
            "genesis:docling_inline",
            "genesis:docling_remote",

            # Data tools
            "genesis:sql_executor",
            "genesis:csv_to_data",
            "genesis:json_to_data"
        ]

        return spec_type in tool_types

    def _get_component_schema_inspector(self):
        """Get ComponentSchemaInspector instance with lazy loading."""
        global _component_schema_inspector

        if _component_schema_inspector is None:
            try:
                from langflow.services.spec.component_schema_inspector import ComponentSchemaInspector
                _component_schema_inspector = ComponentSchemaInspector()
            except ImportError as e:
                logger.warning(f"Could not import ComponentSchemaInspector: {e}")
                _component_schema_inspector = None

        return _component_schema_inspector

    def get_component_io_mapping_enhanced(self) -> Dict[str, Dict[str, Any]]:
        """
        Get enhanced I/O mappings using real component introspection.

        Returns:
            Dictionary mapping component names to their I/O information
        """
        if not self._use_real_introspection:
            return self._get_hardcoded_io_mappings()

        inspector = self._get_component_schema_inspector()
        if inspector is None:
            logger.warning("ComponentSchemaInspector not available, falling back to hardcoded mappings")
            return self._get_hardcoded_io_mappings()

        try:
            # Get real component I/O mappings
            real_mappings = inspector.get_component_io_mapping()

            # Merge with hardcoded mappings (real mappings take precedence)
            hardcoded_mappings = self._get_hardcoded_io_mappings()

            # Start with hardcoded mappings as base
            combined_mappings = hardcoded_mappings.copy()

            # Update with real component data where available
            for component_name, mapping_data in real_mappings.items():
                if component_name in combined_mappings:
                    # Merge real data with hardcoded data
                    combined_mappings[component_name].update(mapping_data)
                    logger.debug(f"Enhanced mapping for {component_name} with real component data")
                else:
                    # Add new component discovered through introspection
                    combined_mappings[component_name] = mapping_data
                    logger.info(f"Added new component mapping from introspection: {component_name}")

            return combined_mappings

        except Exception as e:
            logger.error(f"Error during component introspection: {e}")
            logger.warning("Falling back to hardcoded I/O mappings")
            return self._get_hardcoded_io_mappings()

    def _get_hardcoded_io_mappings(self) -> Dict[str, Dict[str, Any]]:
        """Get the original hardcoded I/O mappings as fallback."""
        io_mappings = {
            "AutonomizeModel": {
                "input_field": "search_query",
                "output_field": "prediction",
                "output_types": ["Data"],
                "input_types": ["str"]
            },
            "ChatInput": {
                "input_field": None,
                "output_field": "message",
                "output_types": ["Message"],
                "input_types": []
            },
            "ChatOutput": {
                "input_field": "input_value",
                "output_field": "message",
                "output_types": ["Message"],
                "input_types": ["Message", "str"]
            },
            "Agent": {
                "input_field": "input_value",
                "output_field": "response",
                "output_types": ["Message"],
                "input_types": ["Message", "str"]
            },
            "AutonomizeAgent": {
                "input_field": "input_value",
                "output_field": "response",
                "output_types": ["Message"],
                "input_types": ["Message", "str"]
            },
            "LanguageModelComponent": {
                "input_field": "input_message",
                "output_field": "message",
                "output_types": ["Message"],
                "input_types": ["Message"]
            },
            "Prompt": {
                "input_field": "template",
                "output_field": "prompt",
                "output_types": ["Message"],
                "input_types": ["str", "Text"]
            },
            "PromptComponent": {
                "input_field": "template",
                "output_field": "prompt",
                "output_types": ["Message"],
                "input_types": ["str", "Text"]
            },
            "GenesisPromptComponent": {
                "input_field": "template",
                "output_field": "prompt",
                "output_types": ["Message"],
                "input_types": ["str", "Text"]
            },
            "MCPTools": {
                "input_field": None,
                "output_field": "response",
                "output_types": ["DataFrame"],
                "input_types": []
            },
            "APIRequest": {
                "input_field": "url_input",
                "output_field": "data",
                "output_types": ["Data"],
                "input_types": ["str"]
            },
            "CustomComponent": {
                "input_field": "input_value",
                "output_field": "output",
                "output_types": ["Any"],
                "input_types": ["any"]
            },
            "Memory": {
                "input_field": "input_value",
                "output_field": "memory",
                "output_types": ["Message"],
                "input_types": ["Message", "str"]
            },
            "OpenAIModel": {
                "input_field": "input_value",
                "output_field": "text_output",
                "output_types": ["Message"],
                "input_types": ["Message", "str"]
            },
            "AzureOpenAIModel": {
                "input_field": "input_value",
                "output_field": "text_output",
                "output_types": ["Message"],
                "input_types": ["Message", "str"]
            },
            "KnowledgeHubSearch": {
                "input_field": "search_query",
                "output_field": "query_results",
                "output_types": ["Data"],
                "input_types": ["str", "Message"]
            },
            "EncoderProTool": {
                "input_field": "default_service_code",
                "output_field": "component_as_tool",
                "output_types": ["Tool"],
                "input_types": ["str", "Data"]
            },
            "FileComponent": {
                "input_field": "file_path",
                "output_field": "data",
                "output_types": ["Data"],
                "input_types": ["str"]
            },
            "File": {
                "input_field": "path",
                "output_field": "data",
                "output_types": ["Document"],
                "input_types": ["str"]
            },
            "Directory": {
                "input_field": "path",
                "output_field": "data",
                "output_types": ["Data"],
                "input_types": ["str"]
            },
            "URL": {
                "input_field": "url",
                "output_field": "data",
                "output_types": ["Data"],
                "input_types": ["str"]
            },
            "CSVToDataComponent": {
                "input_field": "csv_file",
                "output_field": "data",
                "output_types": ["Data"],
                "input_types": ["str", "Document"]
            },
            "JSONToDataComponent": {
                "input_field": "json_string",
                "output_field": "data",
                "output_types": ["Data"],
                "input_types": ["str", "Data"]
            },
            "DoclingInlineComponent": {
                "input_field": "file_path",
                "output_field": "document",
                "output_types": ["Document"],
                "input_types": ["str"]
            },
            "WebSearchComponent": {
                "input_field": "query",
                "output_field": "results",
                "output_types": ["Data"],
                "input_types": ["str", "Message"]
            },
            "SQLExecutor": {
                "input_field": "query",
                "output_field": "results",
                "output_types": ["Data"],
                "input_types": ["str"]
            },
            "CrewAIAgentComponent": {
                "input_field": "input_value",
                "output_field": "response",
                "output_types": ["Message"],
                "input_types": ["Message", "str"]
            }
        }

        return io_mappings

    def get_available_components(self) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """
        Get all available components organized by category.

        Returns:
            Dictionary with categories and their component mappings
        """
        inspector = self._get_component_schema_inspector()

        result = {
            "genesis_mapped": {},  # Genesis spec types mapped to components
            "discovered_components": {}  # Components discovered through introspection
        }

        # Add all genesis mappings
        all_mappings = {**self.AUTONOMIZE_MODELS, **self.MCP_MAPPINGS, **self.STANDARD_MAPPINGS}
        for genesis_type, mapping in all_mappings.items():
            result["genesis_mapped"][genesis_type] = mapping

        # Add discovered components if inspector available
        if inspector:
            try:
                schemas = inspector.get_all_schemas()
                for component_name, schema in schemas.items():
                    result["discovered_components"][component_name] = {
                        "name": schema.name,
                        "class_name": schema.class_name,
                        "module_path": schema.module_path,
                        "description": schema.description,
                        "display_name": schema.display_name,
                        "input_types": schema.input_types,
                        "output_types": schema.output_types,
                        "inputs": schema.inputs,
                        "outputs": schema.outputs,
                        "base_classes": schema.base_classes
                    }
            except Exception as e:
                logger.warning(f"Could not get discovered components: {e}")

        return result

    def validate_component_connection_enhanced(self, source_type: str, target_type: str,
                                             source_output: str, target_input: str) -> Dict[str, Any]:
        """
        Validate connection between components using real component introspection.

        Args:
            source_type: Genesis type of source component
            target_type: Genesis type of target component
            source_output: Output field name
            target_input: Input field name

        Returns:
            Validation result with compatibility information
        """
        inspector = self._get_component_schema_inspector()

        # Map genesis types to component names
        source_mapping = self.map_component(source_type)
        target_mapping = self.map_component(target_type)

        source_component = source_mapping.get("component")
        target_component = target_mapping.get("component")

        if not source_component or not target_component:
            return {
                "valid": False,
                "error": f"Could not map component types: {source_type} -> {target_type}"
            }

        # Try real component validation first
        if inspector and self._use_real_introspection:
            try:
                result = inspector.validate_component_connection(
                    source_component, target_component, source_output, target_input
                )
                if result.get("valid") is not None:  # Got a real validation result
                    return result
            except Exception as e:
                logger.warning(f"Real component validation failed: {e}")

        # Fallback to hardcoded I/O validation
        return self._validate_connection_hardcoded(
            source_component, target_component, source_output, target_input
        )

    def _validate_connection_hardcoded(self, source_component: str, target_component: str,
                                     source_output: str, target_input: str) -> Dict[str, Any]:
        """Fallback validation using hardcoded I/O mappings."""
        hardcoded_mappings = self._get_hardcoded_io_mappings()

        source_io = hardcoded_mappings.get(source_component, {})
        target_io = hardcoded_mappings.get(target_component, {})

        # Check output field exists
        if source_io.get("output_field") != source_output:
            return {
                "valid": False,
                "error": f"Output field {source_output} not found in {source_component}"
            }

        # Check input field exists
        if target_io.get("input_field") != target_input:
            return {
                "valid": False,
                "error": f"Input field {target_input} not found in {target_component}"
            }

        # Check type compatibility
        source_types = source_io.get("output_types", [])
        target_types = target_io.get("input_types", [])

        # Basic compatibility check
        compatible = (
            any(otype in target_types for otype in source_types) or
            "any" in target_types or
            "Any" in target_types
        )

        return {
            "valid": compatible,
            "source_types": source_types,
            "target_types": target_types,
            "error": None if compatible else f"Type mismatch: {source_types} -> {target_types}"
        }

    def enable_real_introspection(self, enabled: bool = True):
        """Enable or disable real component introspection."""
        self._use_real_introspection = enabled
        logger.info(f"Real component introspection {'enabled' if enabled else 'disabled'}")