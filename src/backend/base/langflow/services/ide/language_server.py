"""
Genesis Language Server Protocol Implementation - Phase 4 IDE Integration.

Provides comprehensive LSP support for Genesis specifications including:
- Real-time validation and error reporting
- Auto-completion for Genesis components and fields
- Hover documentation and inline help
- Code actions and quick fixes
- Integration with all Phase 1-3 enhancements
"""

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass

import yaml
from lsprotocol import types as lsp
from pygls.server import LanguageServer
from pygls.workspace import Document

from langflow.services.spec.service import SpecService
from langflow.services.runtime import RuntimeType, ValidationOptions

logger = logging.getLogger(__name__)


@dataclass
class CompletionItem:
    """Enhanced completion item with Genesis-specific metadata."""
    label: str
    kind: lsp.CompletionItemKind
    detail: Optional[str] = None
    documentation: Optional[str] = None
    insert_text: Optional[str] = None
    snippet: bool = False
    genesis_type: Optional[str] = None
    required_fields: Optional[List[str]] = None


class GenesisLanguageServer:
    """
    Language Server for Genesis specifications with Phase 4 enhancements.

    Provides comprehensive IDE support including real-time validation,
    intelligent auto-completion, and integration with enhanced validation system.
    """

    def __init__(self):
        """Initialize the Genesis Language Server."""
        self.server = LanguageServer("genesis-lsp", "1.0.0")
        self.spec_service = SpecService()
        self.document_cache: Dict[str, Document] = {}
        self.validation_cache: Dict[str, Dict[str, Any]] = {}

        # Register LSP handlers
        self._register_handlers()

        # Genesis component metadata for auto-completion
        self.genesis_components = {
            "genesis:chat_input": {
                "description": "Chat input component for receiving user messages",
                "required_fields": ["name"],
                "optional_fields": ["description", "config"],
                "example": {
                    "type": "genesis:chat_input",
                    "name": "User Input",
                    "description": "Receives user queries"
                }
            },
            "genesis:chat_output": {
                "description": "Chat output component for displaying responses",
                "required_fields": ["name"],
                "optional_fields": ["description", "config"],
                "example": {
                    "type": "genesis:chat_output",
                    "name": "Response Output",
                    "description": "Displays final response"
                }
            },
            "genesis:agent": {
                "description": "Single agent component for processing and decision making",
                "required_fields": ["name", "config"],
                "optional_fields": ["description", "asTools", "provides"],
                "example": {
                    "type": "genesis:agent",
                    "name": "Main Agent",
                    "description": "Primary processing agent",
                    "config": {
                        "provider": "Azure OpenAI",
                        "temperature": 0.7
                    }
                }
            },
            "genesis:crewai_agent": {
                "description": "CrewAI agent for multi-agent workflows",
                "required_fields": ["name", "config"],
                "optional_fields": ["description", "asTools", "provides"],
                "example": {
                    "type": "genesis:crewai_agent",
                    "name": "Specialist Agent",
                    "config": {
                        "role": "Data Analyst",
                        "goal": "Analyze data and provide insights",
                        "backstory": "Expert data analyst with domain expertise"
                    }
                }
            },
            "genesis:knowledge_hub_search": {
                "description": "Knowledge search component for information retrieval",
                "required_fields": ["name"],
                "optional_fields": ["description", "config", "asTools"],
                "example": {
                    "type": "genesis:knowledge_hub_search",
                    "name": "Knowledge Search",
                    "asTools": True,
                    "config": {
                        "collections": ["medical", "clinical"]
                    }
                }
            },
            "genesis:mcp_tool": {
                "description": "MCP tool component for external integrations",
                "required_fields": ["name", "config"],
                "optional_fields": ["description", "asTools"],
                "example": {
                    "type": "genesis:mcp_tool",
                    "name": "Healthcare API Tool",
                    "asTools": True,
                    "config": {
                        "tool_name": "healthcare_eligibility_check"
                    }
                }
            },
            "genesis:api_request": {
                "description": "API request component for HTTP integrations",
                "required_fields": ["name", "config"],
                "optional_fields": ["description", "asTools"],
                "example": {
                    "type": "genesis:api_request",
                    "name": "External API",
                    "config": {
                        "method": "POST",
                        "url_input": "https://api.example.com/endpoint"
                    }
                }
            }
        }

    def _register_handlers(self):
        """Register all LSP handlers."""

        @self.server.feature(lsp.TEXT_DOCUMENT_DID_OPEN)
        async def did_open(params: lsp.DidOpenTextDocumentParams):
            """Handle document open event."""
            document = self.server.workspace.get_document(params.text_document.uri)
            self.document_cache[params.text_document.uri] = document
            await self._validate_document(document)

        @self.server.feature(lsp.TEXT_DOCUMENT_DID_CHANGE)
        async def did_change(params: lsp.DidChangeTextDocumentParams):
            """Handle document change event with real-time validation."""
            document = self.server.workspace.get_document(params.text_document.uri)
            self.document_cache[params.text_document.uri] = document
            await self._validate_document(document)

        @self.server.feature(lsp.TEXT_DOCUMENT_DID_SAVE)
        async def did_save(params: lsp.DidSaveTextDocumentParams):
            """Handle document save event."""
            document = self.server.workspace.get_document(params.text_document.uri)
            await self._validate_document(document, comprehensive=True)

        @self.server.feature(lsp.TEXT_DOCUMENT_COMPLETION)
        async def completion(params: lsp.CompletionParams) -> Optional[lsp.CompletionList]:
            """Provide intelligent auto-completion."""
            return await self._provide_completion(params)

        @self.server.feature(lsp.TEXT_DOCUMENT_HOVER)
        async def hover(params: lsp.HoverParams) -> Optional[lsp.Hover]:
            """Provide hover documentation."""
            return await self._provide_hover(params)

        @self.server.feature(lsp.TEXT_DOCUMENT_CODE_ACTION)
        async def code_action(params: lsp.CodeActionParams) -> Optional[List[lsp.CodeAction]]:
            """Provide code actions and quick fixes."""
            return await self._provide_code_actions(params)

        @self.server.feature(lsp.TEXT_DOCUMENT_DIAGNOSTIC)
        async def diagnostic(params: lsp.DocumentDiagnosticParams) -> lsp.DocumentDiagnosticReport:
            """Provide diagnostic information."""
            return await self._provide_diagnostics(params)

    async def _validate_document(self, document: Document, comprehensive: bool = False) -> None:
        """
        Validate Genesis specification document with Phase 3 enhancements.

        Args:
            document: LSP document to validate
            comprehensive: Whether to perform comprehensive validation
        """
        try:
            # Parse YAML content
            spec_content = document.source

            # Use enhanced validation from Phase 3
            if comprehensive:
                validation_result = await self.spec_service.validate_spec_with_runtime(
                    spec_content,
                    RuntimeType.LANGFLOW,
                    ValidationOptions(
                        strict_mode=True,
                        performance_checks=True,
                        detailed_errors=True
                    )
                )
            else:
                validation_result = await self.spec_service.validate_spec_quick(spec_content)

            # Cache validation result
            self.validation_cache[document.uri] = validation_result

            # Convert to LSP diagnostics
            diagnostics = self._convert_to_diagnostics(validation_result, document)

            # Publish diagnostics
            self.server.publish_diagnostics(document.uri, diagnostics)

        except Exception as e:
            logger.error(f"Error validating document {document.uri}: {e}")

            # Send error diagnostic
            error_diagnostic = lsp.Diagnostic(
                range=lsp.Range(
                    start=lsp.Position(line=0, character=0),
                    end=lsp.Position(line=0, character=len(document.lines[0]) if document.lines else 0)
                ),
                message=f"Validation error: {e}",
                severity=lsp.DiagnosticSeverity.Error,
                source="genesis-lsp"
            )

            self.server.publish_diagnostics(document.uri, [error_diagnostic])

    def _convert_to_diagnostics(
        self,
        validation_result: Dict[str, Any],
        document: Document
    ) -> List[lsp.Diagnostic]:
        """
        Convert validation results to LSP diagnostics.

        Args:
            validation_result: Validation result from SpecService
            document: Source document

        Returns:
            List of LSP diagnostics
        """
        diagnostics = []

        # Process errors
        for error in validation_result.get("errors", []):
            diagnostic = self._create_diagnostic(error, document, lsp.DiagnosticSeverity.Error)
            if diagnostic:
                diagnostics.append(diagnostic)

        # Process warnings
        for warning in validation_result.get("warnings", []):
            diagnostic = self._create_diagnostic(warning, document, lsp.DiagnosticSeverity.Warning)
            if diagnostic:
                diagnostics.append(diagnostic)

        # Process suggestions as information
        for suggestion in validation_result.get("suggestions", []):
            diagnostic = self._create_diagnostic(suggestion, document, lsp.DiagnosticSeverity.Information)
            if diagnostic:
                diagnostics.append(diagnostic)

        return diagnostics

    def _create_diagnostic(
        self,
        issue: Union[str, Dict[str, Any]],
        document: Document,
        severity: lsp.DiagnosticSeverity
    ) -> Optional[lsp.Diagnostic]:
        """
        Create LSP diagnostic from validation issue.

        Args:
            issue: Validation issue (string or dictionary)
            document: Source document
            severity: Diagnostic severity

        Returns:
            LSP diagnostic or None if creation fails
        """
        try:
            if isinstance(issue, str):
                message = issue
                component_id = None
            else:
                message = issue.get("message", str(issue))
                component_id = issue.get("component_id")

            # Find position in document
            position_range = self._find_issue_position(document, component_id, message)

            diagnostic = lsp.Diagnostic(
                range=position_range,
                message=message,
                severity=severity,
                source="genesis-lsp"
            )

            # Add code and related information if available
            if isinstance(issue, dict):
                if issue.get("code"):
                    diagnostic.code = issue["code"]

                if issue.get("suggestion"):
                    # Add suggestion as related information
                    diagnostic.related_information = [
                        lsp.DiagnosticRelatedInformation(
                            location=lsp.Location(uri=document.uri, range=position_range),
                            message=f"Suggestion: {issue['suggestion']}"
                        )
                    ]

            return diagnostic

        except Exception as e:
            logger.warning(f"Error creating diagnostic: {e}")
            return None

    def _find_issue_position(
        self,
        document: Document,
        component_id: Optional[str],
        message: str
    ) -> lsp.Range:
        """
        Find position of issue in document for accurate error highlighting.

        Args:
            document: Source document
            component_id: Component ID if issue is component-specific
            message: Error message

        Returns:
            Range indicating position of the issue
        """
        try:
            lines = document.lines

            # If component_id is specified, find that component
            if component_id:
                for line_num, line in enumerate(lines):
                    if component_id in line and (":" in line or "-" in line):
                        # Found component line
                        start_char = max(0, line.find(component_id))
                        end_char = min(len(line), start_char + len(component_id))

                        return lsp.Range(
                            start=lsp.Position(line=line_num, character=start_char),
                            end=lsp.Position(line=line_num, character=end_char)
                        )

            # Search for keywords from the message
            keywords = ["type", "components", "provides", "config"]
            for keyword in keywords:
                if keyword in message.lower():
                    for line_num, line in enumerate(lines):
                        if keyword in line.lower():
                            start_char = max(0, line.lower().find(keyword))
                            end_char = min(len(line), start_char + len(keyword))

                            return lsp.Range(
                                start=lsp.Position(line=line_num, character=start_char),
                                end=lsp.Position(line=line_num, character=end_char)
                            )

            # Default to first line if no specific position found
            return lsp.Range(
                start=lsp.Position(line=0, character=0),
                end=lsp.Position(line=0, character=len(lines[0]) if lines else 0)
            )

        except Exception as e:
            logger.warning(f"Error finding issue position: {e}")
            return lsp.Range(
                start=lsp.Position(line=0, character=0),
                end=lsp.Position(line=0, character=0)
            )

    async def _provide_completion(self, params: lsp.CompletionParams) -> Optional[lsp.CompletionList]:
        """
        Provide intelligent auto-completion for Genesis specifications.

        Args:
            params: Completion parameters from LSP client

        Returns:
            Completion list with Genesis-specific suggestions
        """
        try:
            document = self.server.workspace.get_document(params.text_document.uri)
            line = document.lines[params.position.line]
            character = params.position.character

            # Get context around cursor
            prefix = line[:character]
            suffix = line[character:]

            completion_items = []

            # Type completion (when user types "type:")
            if "type:" in prefix and prefix.strip().endswith("type:"):
                completion_items.extend(self._get_component_type_completions())

            # Field completion based on context
            elif self._is_in_component_context(document, params.position):
                completion_items.extend(self._get_field_completions(document, params.position))

            # Value completion
            elif self._is_in_value_context(prefix):
                completion_items.extend(self._get_value_completions(prefix))

            # Structure completion
            elif self._should_suggest_structure(document, params.position):
                completion_items.extend(self._get_structure_completions())

            return lsp.CompletionList(
                is_incomplete=False,
                items=[self._convert_completion_item(item) for item in completion_items]
            )

        except Exception as e:
            logger.error(f"Error providing completion: {e}")
            return None

    def _get_component_type_completions(self) -> List[CompletionItem]:
        """Get completions for Genesis component types."""
        completions = []

        for comp_type, metadata in self.genesis_components.items():
            completion = CompletionItem(
                label=comp_type,
                kind=lsp.CompletionItemKind.Class,
                detail=metadata["description"],
                documentation=self._format_component_documentation(comp_type, metadata),
                insert_text=comp_type,
                genesis_type=comp_type,
                required_fields=metadata["required_fields"]
            )
            completions.append(completion)

        return completions

    def _get_field_completions(self, document: Document, position: lsp.Position) -> List[CompletionItem]:
        """Get field completions based on current component context."""
        completions = []

        # Determine current component type
        current_component_type = self._get_current_component_type(document, position)

        if current_component_type and current_component_type in self.genesis_components:
            metadata = self.genesis_components[current_component_type]

            # Add required fields
            for field in metadata["required_fields"]:
                completions.append(CompletionItem(
                    label=field,
                    kind=lsp.CompletionItemKind.Field,
                    detail=f"Required field for {current_component_type}",
                    insert_text=f"{field}: "
                ))

            # Add optional fields
            for field in metadata["optional_fields"]:
                completions.append(CompletionItem(
                    label=field,
                    kind=lsp.CompletionItemKind.Field,
                    detail=f"Optional field for {current_component_type}",
                    insert_text=f"{field}: "
                ))

        # Add common fields
        common_fields = [
            ("name", "Component display name"),
            ("description", "Component description"),
            ("config", "Component configuration"),
            ("provides", "Component output connections"),
            ("asTools", "Mark component as tool")
        ]

        for field, desc in common_fields:
            completions.append(CompletionItem(
                label=field,
                kind=lsp.CompletionItemKind.Field,
                detail=desc,
                insert_text=f"{field}: "
            ))

        return completions

    def _get_value_completions(self, prefix: str) -> List[CompletionItem]:
        """Get value completions based on field context."""
        completions = []

        # Provider completions
        if "provider:" in prefix:
            providers = ["Azure OpenAI", "OpenAI", "Anthropic", "Local"]
            for provider in providers:
                completions.append(CompletionItem(
                    label=provider,
                    kind=lsp.CompletionItemKind.Value,
                    detail="LLM provider",
                    insert_text=f'"{provider}"'
                ))

        # Boolean completions
        elif any(field in prefix for field in ["asTools:", "stream:", "verbose:"]):
            for value in ["true", "false"]:
                completions.append(CompletionItem(
                    label=value,
                    kind=lsp.CompletionItemKind.Value,
                    detail="Boolean value",
                    insert_text=value
                ))

        # UseAs completions
        elif "useAs:" in prefix:
            use_as_values = ["input", "tools", "system_prompt", "response", "memory"]
            for value in use_as_values:
                completions.append(CompletionItem(
                    label=value,
                    kind=lsp.CompletionItemKind.Value,
                    detail="Connection type",
                    insert_text=f'"{value}"'
                ))

        return completions

    def _get_structure_completions(self) -> List[CompletionItem]:
        """Get structure completions for Genesis specifications."""
        completions = []

        # Top-level structure
        top_level_fields = [
            ("id", "urn:agent:genesis:domain:name:version"),
            ("name", "Specification name"),
            ("description", "Specification description"),
            ("agentGoal", "Primary agent objective"),
            ("kind", "Single Agent or Multi Agent"),
            ("components", "Workflow components")
        ]

        for field, desc in top_level_fields:
            completions.append(CompletionItem(
                label=field,
                kind=lsp.CompletionItemKind.Field,
                detail=desc,
                insert_text=f"{field}: "
            ))

        return completions

    def _convert_completion_item(self, item: CompletionItem) -> lsp.CompletionItem:
        """Convert internal completion item to LSP format."""
        lsp_item = lsp.CompletionItem(
            label=item.label,
            kind=item.kind,
            detail=item.detail,
            documentation=item.documentation,
            insert_text=item.insert_text or item.label
        )

        if item.snippet:
            lsp_item.insert_text_format = lsp.InsertTextFormat.Snippet

        return lsp_item

    async def _provide_hover(self, params: lsp.HoverParams) -> Optional[lsp.Hover]:
        """
        Provide hover documentation for Genesis specifications.

        Args:
            params: Hover parameters from LSP client

        Returns:
            Hover information with documentation
        """
        try:
            document = self.server.workspace.get_document(params.text_document.uri)
            line = document.lines[params.position.line]
            word = self._get_word_at_position(line, params.position.character)

            # Check if hovering over Genesis component type
            if word in self.genesis_components:
                metadata = self.genesis_components[word]
                documentation = self._format_component_documentation(word, metadata)

                return lsp.Hover(
                    contents=lsp.MarkupContent(
                        kind=lsp.MarkupKind.Markdown,
                        value=documentation
                    ),
                    range=self._get_word_range(document, params.position, word)
                )

            # Check for field-specific documentation
            field_docs = {
                "asTools": "Mark this component as available for use as a tool by agents",
                "provides": "Define how this component's output connects to other components",
                "useAs": "Specify how the connected component should use this output",
                "provider": "Specify the AI model provider (Azure OpenAI, OpenAI, etc.)",
                "temperature": "Control randomness in AI responses (0.0 = deterministic, 1.0 = creative)"
            }

            if word in field_docs:
                return lsp.Hover(
                    contents=lsp.MarkupContent(
                        kind=lsp.MarkupKind.Markdown,
                        value=f"**{word}**: {field_docs[word]}"
                    )
                )

            return None

        except Exception as e:
            logger.error(f"Error providing hover: {e}")
            return None

    async def _provide_code_actions(self, params: lsp.CodeActionParams) -> Optional[List[lsp.CodeAction]]:
        """
        Provide code actions and quick fixes.

        Args:
            params: Code action parameters

        Returns:
            List of available code actions
        """
        try:
            document = self.server.workspace.get_document(params.text_document.uri)
            actions = []

            # Get validation results for context
            validation_result = self.validation_cache.get(document.uri, {})

            # Quick fix actions based on errors
            for diagnostic in params.context.diagnostics:
                if diagnostic.source == "genesis-lsp":
                    action = self._create_quick_fix_action(diagnostic, document)
                    if action:
                        actions.append(action)

            # General code actions
            actions.extend([
                self._create_format_action(document),
                self._create_validate_action(document),
                self._create_convert_action(document)
            ])

            return actions

        except Exception as e:
            logger.error(f"Error providing code actions: {e}")
            return None

    async def _provide_diagnostics(self, params: lsp.DocumentDiagnosticParams) -> lsp.DocumentDiagnosticReport:
        """
        Provide diagnostic information for document.

        Args:
            params: Diagnostic parameters

        Returns:
            Document diagnostic report
        """
        try:
            document = self.server.workspace.get_document(params.text_document.uri)

            # Get cached validation result or perform new validation
            validation_result = self.validation_cache.get(document.uri)
            if not validation_result:
                await self._validate_document(document)
                validation_result = self.validation_cache.get(document.uri, {})

            # Convert to diagnostics
            diagnostics = self._convert_to_diagnostics(validation_result, document)

            return lsp.DocumentDiagnosticReport(
                kind=lsp.DocumentDiagnosticReportKind.Full,
                items=diagnostics
            )

        except Exception as e:
            logger.error(f"Error providing diagnostics: {e}")
            return lsp.DocumentDiagnosticReport(
                kind=lsp.DocumentDiagnosticReportKind.Full,
                items=[]
            )

    # Helper methods

    def _format_component_documentation(self, comp_type: str, metadata: Dict[str, Any]) -> str:
        """Format component documentation for hover display."""
        doc = f"## {comp_type}\n\n"
        doc += f"{metadata['description']}\n\n"

        doc += "### Required Fields:\n"
        for field in metadata["required_fields"]:
            doc += f"- `{field}`\n"

        doc += "\n### Optional Fields:\n"
        for field in metadata["optional_fields"]:
            doc += f"- `{field}`\n"

        doc += "\n### Example:\n```yaml\n"
        example = metadata["example"]
        doc += yaml.dump(example, default_flow_style=False)
        doc += "```"

        return doc

    def _is_in_component_context(self, document: Document, position: lsp.Position) -> bool:
        """Check if cursor is within a component definition."""
        # Simple heuristic - look for indented content under a component
        current_line = document.lines[position.line]
        return current_line.startswith("  ") or current_line.startswith("\t")

    def _is_in_value_context(self, prefix: str) -> bool:
        """Check if cursor is in a value context (after ':')."""
        return ":" in prefix and not prefix.strip().endswith(":")

    def _should_suggest_structure(self, document: Document, position: lsp.Position) -> bool:
        """Check if structure suggestions should be provided."""
        # At beginning of line with no indentation
        line = document.lines[position.line]
        return position.character <= len(line) - len(line.lstrip())

    def _get_current_component_type(self, document: Document, position: lsp.Position) -> Optional[str]:
        """Determine the component type at current position."""
        # Look backwards from current position to find component type
        for line_num in range(position.line, -1, -1):
            line = document.lines[line_num]
            if "type:" in line:
                for comp_type in self.genesis_components.keys():
                    if comp_type in line:
                        return comp_type
        return None

    def _get_word_at_position(self, line: str, character: int) -> str:
        """Extract word at given character position."""
        # Find word boundaries
        start = character
        while start > 0 and (line[start - 1].isalnum() or line[start - 1] in "_:"):
            start -= 1

        end = character
        while end < len(line) and (line[end].isalnum() or line[end] in "_:"):
            end += 1

        return line[start:end]

    def _get_word_range(self, document: Document, position: lsp.Position, word: str) -> lsp.Range:
        """Get range for word at position."""
        line = document.lines[position.line]
        start_char = max(0, line.find(word, max(0, position.character - len(word))))
        end_char = min(len(line), start_char + len(word))

        return lsp.Range(
            start=lsp.Position(line=position.line, character=start_char),
            end=lsp.Position(line=position.line, character=end_char)
        )

    def _create_quick_fix_action(self, diagnostic: lsp.Diagnostic, document: Document) -> Optional[lsp.CodeAction]:
        """Create quick fix action for diagnostic."""
        try:
            # Extract suggestions from diagnostic
            message = diagnostic.message.lower()

            if "missing required field" in message:
                return self._create_add_field_action(diagnostic, document)
            elif "invalid component type" in message:
                return self._create_fix_component_type_action(diagnostic, document)

            return None

        except Exception as e:
            logger.warning(f"Error creating quick fix: {e}")
            return None

    def _create_add_field_action(self, diagnostic: lsp.Diagnostic, document: Document) -> lsp.CodeAction:
        """Create action to add missing required field."""
        return lsp.CodeAction(
            title="Add missing required field",
            kind=lsp.CodeActionKind.QuickFix,
            diagnostics=[diagnostic],
            edit=lsp.WorkspaceEdit(
                changes={
                    document.uri: [
                        lsp.TextEdit(
                            range=diagnostic.range,
                            new_text="# TODO: Add required field"
                        )
                    ]
                }
            )
        )

    def _create_fix_component_type_action(self, diagnostic: lsp.Diagnostic, document: Document) -> lsp.CodeAction:
        """Create action to fix invalid component type."""
        return lsp.CodeAction(
            title="Fix component type",
            kind=lsp.CodeActionKind.QuickFix,
            diagnostics=[diagnostic]
        )

    def _create_format_action(self, document: Document) -> lsp.CodeAction:
        """Create format document action."""
        return lsp.CodeAction(
            title="Format Genesis specification",
            kind=lsp.CodeActionKind.SourceFixAll
        )

    def _create_validate_action(self, document: Document) -> lsp.CodeAction:
        """Create validate document action."""
        return lsp.CodeAction(
            title="Validate Genesis specification",
            kind=lsp.CodeActionKind.Source
        )

    def _create_convert_action(self, document: Document) -> lsp.CodeAction:
        """Create convert specification action."""
        return lsp.CodeAction(
            title="Convert to Langflow",
            kind=lsp.CodeActionKind.Source
        )


def start_language_server(port: int = 8080) -> None:
    """
    Start the Genesis Language Server.

    Args:
        port: Port to run the language server on
    """
    try:
        # Create and start the language server
        genesis_server = GenesisLanguageServer()

        logger.info(f"Starting Genesis Language Server on port {port}")

        # Start the server
        genesis_server.server.start_tcp("localhost", port)

    except Exception as e:
        logger.error(f"Error starting language server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Start the language server
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    start_language_server(port)