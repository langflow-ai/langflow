"""
VS Code Extension Generator for Genesis Specification Development - Phase 4.

Generates VS Code extension configuration and assets for Genesis specification development
with comprehensive LSP integration and enhanced development experience.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)


class VSCodeExtensionGenerator:
    """
    Generator for VS Code extension supporting Genesis specifications.

    Creates comprehensive VS Code extension with:
    - Syntax highlighting for Genesis YAML
    - LSP client integration
    - Snippets and templates
    - Commands and keybindings
    - Theme integration
    """

    def __init__(self, extension_name: str = "genesis-specifications"):
        """
        Initialize VS Code extension generator.

        Args:
            extension_name: Name of the extension
        """
        self.extension_name = extension_name
        self.extension_id = f"autonomize.{extension_name}"

    def generate_extension(self, output_dir: str) -> Dict[str, str]:
        """
        Generate complete VS Code extension.

        Args:
            output_dir: Output directory for extension files

        Returns:
            Dictionary mapping file paths to generated content
        """
        extension_path = Path(output_dir) / self.extension_name
        extension_path.mkdir(parents=True, exist_ok=True)

        generated_files = {}

        # Generate core extension files
        generated_files.update(self._generate_package_json(extension_path))
        generated_files.update(self._generate_extension_js(extension_path))
        generated_files.update(self._generate_language_config(extension_path))
        generated_files.update(self._generate_syntax_highlighting(extension_path))
        generated_files.update(self._generate_snippets(extension_path))
        generated_files.update(self._generate_themes(extension_path))
        generated_files.update(self._generate_documentation(extension_path))

        logger.info(f"Generated VS Code extension in: {extension_path}")
        return generated_files

    def _generate_package_json(self, extension_path: Path) -> Dict[str, str]:
        """Generate package.json for VS Code extension."""
        package_config = {
            "name": self.extension_name,
            "displayName": "Genesis Specifications",
            "description": "Advanced support for Genesis AI agent specifications with LSP integration",
            "version": "1.0.0",
            "publisher": "autonomize",
            "repository": {
                "type": "git",
                "url": "https://github.com/autonomize-ai/genesis-vscode"
            },
            "engines": {
                "vscode": "^1.80.0"
            },
            "categories": [
                "Programming Languages",
                "Snippets",
                "Linters",
                "Other"
            ],
            "keywords": [
                "genesis",
                "ai-agents",
                "langflow",
                "yaml",
                "specifications",
                "autonomize"
            ],
            "activationEvents": [
                "onLanguage:genesis-yaml"
            ],
            "main": "./extension.js",
            "contributes": {
                "languages": [
                    {
                        "id": "genesis-yaml",
                        "aliases": ["Genesis YAML", "genesis"],
                        "extensions": [".genesis.yaml", ".genesis.yml"],
                        "configuration": "./language-configuration.json",
                        "icon": {
                            "light": "./icons/genesis-light.svg",
                            "dark": "./icons/genesis-dark.svg"
                        }
                    }
                ],
                "grammars": [
                    {
                        "language": "genesis-yaml",
                        "scopeName": "source.genesis.yaml",
                        "path": "./syntaxes/genesis.tmLanguage.json"
                    }
                ],
                "snippets": [
                    {
                        "language": "genesis-yaml",
                        "path": "./snippets/genesis.json"
                    }
                ],
                "themes": [
                    {
                        "label": "Genesis Dark",
                        "uiTheme": "vs-dark",
                        "path": "./themes/genesis-dark.json"
                    },
                    {
                        "label": "Genesis Light",
                        "uiTheme": "vs",
                        "path": "./themes/genesis-light.json"
                    }
                ],
                "commands": [
                    {
                        "command": "genesis.validate",
                        "title": "Validate Genesis Specification",
                        "category": "Genesis"
                    },
                    {
                        "command": "genesis.convert",
                        "title": "Convert to Langflow",
                        "category": "Genesis"
                    },
                    {
                        "command": "genesis.create",
                        "title": "Create New Specification",
                        "category": "Genesis"
                    },
                    {
                        "command": "genesis.preview",
                        "title": "Preview Flow",
                        "category": "Genesis"
                    },
                    {
                        "command": "genesis.format",
                        "title": "Format Document",
                        "category": "Genesis"
                    }
                ],
                "keybindings": [
                    {
                        "command": "genesis.validate",
                        "key": "ctrl+shift+v",
                        "mac": "cmd+shift+v",
                        "when": "editorTextFocus && resourceExtname =~ /\\.(genesis\\.)?(yaml|yml)$/"
                    },
                    {
                        "command": "genesis.convert",
                        "key": "ctrl+shift+c",
                        "mac": "cmd+shift+c",
                        "when": "editorTextFocus && resourceExtname =~ /\\.(genesis\\.)?(yaml|yml)$/"
                    }
                ],
                "menus": {
                    "editor/context": [
                        {
                            "command": "genesis.validate",
                            "when": "resourceExtname =~ /\\.(genesis\\.)?(yaml|yml)$/",
                            "group": "genesis@1"
                        },
                        {
                            "command": "genesis.convert",
                            "when": "resourceExtname =~ /\\.(genesis\\.)?(yaml|yml)$/",
                            "group": "genesis@2"
                        },
                        {
                            "command": "genesis.preview",
                            "when": "resourceExtname =~ /\\.(genesis\\.)?(yaml|yml)$/",
                            "group": "genesis@3"
                        }
                    ],
                    "explorer/context": [
                        {
                            "command": "genesis.create",
                            "when": "explorerResourceIsFolder",
                            "group": "genesis@1"
                        }
                    ]
                },
                "configuration": {
                    "title": "Genesis Specifications",
                    "properties": {
                        "genesis.validation.enabled": {
                            "type": "boolean",
                            "default": True,
                            "description": "Enable real-time validation"
                        },
                        "genesis.validation.mode": {
                            "type": "string",
                            "enum": ["quick", "comprehensive", "runtime"],
                            "default": "comprehensive",
                            "description": "Validation mode"
                        },
                        "genesis.lsp.enabled": {
                            "type": "boolean",
                            "default": True,
                            "description": "Enable Language Server Protocol support"
                        },
                        "genesis.lsp.port": {
                            "type": "number",
                            "default": 8080,
                            "description": "LSP server port"
                        },
                        "genesis.conversion.defaultRuntime": {
                            "type": "string",
                            "enum": ["langflow", "temporal", "kafka"],
                            "default": "langflow",
                            "description": "Default conversion target"
                        },
                        "genesis.completion.enabled": {
                            "type": "boolean",
                            "default": True,
                            "description": "Enable auto-completion"
                        },
                        "genesis.completion.includeSnippets": {
                            "type": "boolean",
                            "default": True,
                            "description": "Include code snippets in completion"
                        }
                    }
                }
            },
            "scripts": {
                "vscode:prepublish": "npm run compile",
                "compile": "tsc -p ./",
                "watch": "tsc -watch -p ./"
            },
            "devDependencies": {
                "@types/node": "^18.0.0",
                "@types/vscode": "^1.80.0",
                "typescript": "^5.0.0"
            },
            "dependencies": {
                "vscode-languageclient": "^8.0.0",
                "yaml": "^2.0.0"
            }
        }

        package_path = extension_path / "package.json"
        with open(package_path, 'w') as f:
            json.dump(package_config, f, indent=2)

        return {str(package_path): json.dumps(package_config, indent=2)}

    def _generate_extension_js(self, extension_path: Path) -> Dict[str, str]:
        """Generate main extension.js file."""
        extension_code = '''
const vscode = require('vscode');
const { LanguageClient, TransportKind } = require('vscode-languageclient/node');

let client;

function activate(context) {
    console.log('Genesis Specifications extension is now active!');

    // Register commands
    registerCommands(context);

    // Start Language Server if enabled
    const config = vscode.workspace.getConfiguration('genesis');
    if (config.get('lsp.enabled')) {
        startLanguageServer(context);
    }

    // Register providers
    registerProviders(context);
}

function registerCommands(context) {
    // Validate command
    const validateCommand = vscode.commands.registerCommand('genesis.validate', async () => {
        const activeEditor = vscode.window.activeTextEditor;
        if (!activeEditor) {
            vscode.window.showErrorMessage('No active Genesis specification file');
            return;
        }

        vscode.window.showInformationMessage('Validating Genesis specification...');
        // Validation will be handled by LSP
    });

    // Convert command
    const convertCommand = vscode.commands.registerCommand('genesis.convert', async () => {
        const activeEditor = vscode.window.activeTextEditor;
        if (!activeEditor) {
            vscode.window.showErrorMessage('No active Genesis specification file');
            return;
        }

        const config = vscode.workspace.getConfiguration('genesis');
        const runtime = config.get('conversion.defaultRuntime');

        vscode.window.showInformationMessage(`Converting to ${runtime}...`);
        // Conversion will be handled by LSP or external command
    });

    // Create new specification command
    const createCommand = vscode.commands.registerCommand('genesis.create', async (uri) => {
        const folderPath = uri ? uri.fsPath : vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
        if (!folderPath) {
            vscode.window.showErrorMessage('No workspace folder available');
            return;
        }

        const specName = await vscode.window.showInputBox({
            prompt: 'Enter specification name',
            placeholder: 'my-agent-spec'
        });

        if (specName) {
            createNewSpecification(folderPath, specName);
        }
    });

    // Preview command
    const previewCommand = vscode.commands.registerCommand('genesis.preview', async () => {
        const activeEditor = vscode.window.activeTextEditor;
        if (!activeEditor) {
            vscode.window.showErrorMessage('No active Genesis specification file');
            return;
        }

        // Create preview panel
        const panel = vscode.window.createWebviewPanel(
            'genesisPreview',
            'Genesis Flow Preview',
            vscode.ViewColumn.Beside,
            {
                enableScripts: true
            }
        );

        panel.webview.html = getPreviewHtml(activeEditor.document.getText());
    });

    // Format command
    const formatCommand = vscode.commands.registerCommand('genesis.format', async () => {
        await vscode.commands.executeCommand('editor.action.formatDocument');
    });

    context.subscriptions.push(
        validateCommand,
        convertCommand,
        createCommand,
        previewCommand,
        formatCommand
    );
}

function startLanguageServer(context) {
    const config = vscode.workspace.getConfiguration('genesis');
    const port = config.get('lsp.port', 8080);

    // Language server options
    const serverOptions = {
        command: 'python',
        args: ['-m', 'langflow.services.ide.language_server', port.toString()],
        transport: TransportKind.stdio
    };

    // Client options
    const clientOptions = {
        documentSelector: [
            { scheme: 'file', language: 'genesis-yaml' },
            { scheme: 'file', pattern: '**/*.genesis.yaml' },
            { scheme: 'file', pattern: '**/*.genesis.yml' }
        ],
        synchronize: {
            fileEvents: vscode.workspace.createFileSystemWatcher('**/*.{genesis.yaml,genesis.yml}')
        }
    };

    // Create and start the language client
    client = new LanguageClient(
        'genesisLanguageServer',
        'Genesis Language Server',
        serverOptions,
        clientOptions
    );

    client.start();
    context.subscriptions.push(client);

    vscode.window.showInformationMessage('Genesis Language Server started');
}

function registerProviders(context) {
    // Document formatter
    const formatterProvider = vscode.languages.registerDocumentFormattingEditProvider(
        'genesis-yaml',
        {
            provideDocumentFormattingEdits(document) {
                // Basic YAML formatting
                const yaml = require('yaml');
                try {
                    const parsed = yaml.parse(document.getText());
                    const formatted = yaml.stringify(parsed, { lineWidth: 100 });

                    return [
                        vscode.TextEdit.replace(
                            new vscode.Range(0, 0, document.lineCount, 0),
                            formatted
                        )
                    ];
                } catch (error) {
                    vscode.window.showErrorMessage(`Formatting error: ${error.message}`);
                    return [];
                }
            }
        }
    );

    context.subscriptions.push(formatterProvider);
}

function createNewSpecification(folderPath, specName) {
    const fs = require('fs');
    const path = require('path');

    const template = `id: urn:agent:genesis:autonomize.ai:${specName}:1.0.0
name: ${specName.replace(/-/g, ' ').replace(/\\b\\w/g, l => l.toUpperCase())}
description: TODO: Add description
agentGoal: TODO: Define agent goal
kind: Single Agent
targetUser: internal
valueGeneration: ProcessAutomation

components:
  input:
    type: genesis:chat_input
    name: User Input
    description: Receives user queries
    provides:
    - useAs: input
      in: agent
      description: User input to agent

  agent:
    type: genesis:agent
    name: Main Agent
    description: Primary processing agent
    config:
      provider: Azure OpenAI
      temperature: 0.7
    provides:
    - useAs: response
      in: output
      description: Agent response to output

  output:
    type: genesis:chat_output
    name: Response Output
    description: Displays the final response

outputs:
- name: response
  type: Message
  description: Final agent response
`;

    const filePath = path.join(folderPath, `${specName}.genesis.yaml`);

    fs.writeFileSync(filePath, template);

    vscode.workspace.openTextDocument(filePath).then(doc => {
        vscode.window.showTextDocument(doc);
    });

    vscode.window.showInformationMessage(`Created Genesis specification: ${specName}.genesis.yaml`);
}

function getPreviewHtml(specContent) {
    return `
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Genesis Flow Preview</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
        .preview-container { padding: 20px; }
        .component {
            border: 1px solid #ccc;
            border-radius: 8px;
            padding: 10px;
            margin: 10px 0;
            background: #f5f5f5;
        }
        .component-title { font-weight: bold; color: #0066cc; }
        .component-type { font-size: 0.9em; color: #666; }
        .connections { margin-top: 10px; }
        .connection {
            background: #e6f3ff;
            padding: 5px;
            border-radius: 4px;
            margin: 2px 0;
            font-size: 0.9em;
        }
    </style>
</head>
<body>
    <div class="preview-container">
        <h2>Genesis Flow Preview</h2>
        <div id="flow-diagram">
            <!-- Flow visualization will be generated here -->
            <p>Flow preview is being generated...</p>
        </div>
    </div>

    <script>
        // Simple flow visualization
        const specContent = \`${specContent.replace(/`/g, '\\`')}\`;

        try {
            // Parse YAML (simplified)
            const lines = specContent.split('\\n');
            let inComponents = false;
            let currentComponent = null;
            const components = {};

            lines.forEach(line => {
                if (line.trim() === 'components:') {
                    inComponents = true;
                    return;
                }

                if (inComponents && line.match(/^\\s{2}\\w+:/)) {
                    currentComponent = line.trim().replace(':', '');
                    components[currentComponent] = { name: currentComponent, type: '', connections: [] };
                }

                if (currentComponent && line.includes('type:')) {
                    components[currentComponent].type = line.split(':')[1].trim();
                }

                if (currentComponent && line.includes('name:')) {
                    components[currentComponent].name = line.split(':')[1].trim();
                }

                if (currentComponent && line.includes('useAs:')) {
                    const useAs = line.split(':')[1].trim();
                    components[currentComponent].connections.push(useAs);
                }
            });

            // Render components
            const container = document.getElementById('flow-diagram');
            container.innerHTML = '';

            Object.entries(components).forEach(([id, component]) => {
                const div = document.createElement('div');
                div.className = 'component';
                div.innerHTML = \`
                    <div class="component-title">\${component.name}</div>
                    <div class="component-type">\${component.type}</div>
                    \${component.connections.length > 0 ?
                        '<div class="connections">' +
                        component.connections.map(conn => \`<div class="connection">→ \${conn}</div>\`).join('') +
                        '</div>' : ''
                    }
                \`;
                container.appendChild(div);
            });

        } catch (error) {
            document.getElementById('flow-diagram').innerHTML = \`<p>Error parsing specification: \${error.message}</p>\`;
        }
    </script>
</body>
</html>
    `;
}

function deactivate() {
    if (client) {
        return client.stop();
    }
}

module.exports = {
    activate,
    deactivate
};
'''

        extension_file = extension_path / "extension.js"
        with open(extension_file, 'w') as f:
            f.write(extension_code)

        return {str(extension_file): extension_code}

    def _generate_language_config(self, extension_path: Path) -> Dict[str, str]:
        """Generate language configuration for Genesis YAML."""
        language_config = {
            "comments": {
                "lineComment": "#"
            },
            "brackets": [
                ["{", "}"],
                ["[", "]"],
                ["(", ")"]
            ],
            "autoClosingPairs": [
                {"open": "{", "close": "}"},
                {"open": "[", "close": "]"},
                {"open": "(", "close": ")"},
                {"open": "\"", "close": "\"", "notIn": ["string"]},
                {"open": "'", "close": "'", "notIn": ["string", "comment"]}
            ],
            "surroundingPairs": [
                ["{", "}"],
                ["[", "]"],
                ["(", ")"],
                ["\"", "\""],
                ["'", "'"]
            ],
            "indentationRules": {
                "increaseIndentPattern": "^\\s*.*(:|-) $",
                "decreaseIndentPattern": "^\\s+\\S.*$"
            },
            "wordPattern": "(-?\\d*\\.\\d\\w*)|([^\\`\\~\\!\\@\\#\\%\\^\\&\\*\\(\\)\\-\\=\\+\\[\\{\\]\\}\\\\\\|\\;\\:\\'\\\"\\,\\.\\<\\>\\/\\?\\s]+)"
        }

        config_file = extension_path / "language-configuration.json"
        with open(config_file, 'w') as f:
            json.dump(language_config, f, indent=2)

        return {str(config_file): json.dumps(language_config, indent=2)}

    def _generate_syntax_highlighting(self, extension_path: Path) -> Dict[str, str]:
        """Generate TextMate grammar for syntax highlighting."""
        syntaxes_dir = extension_path / "syntaxes"
        syntaxes_dir.mkdir(exist_ok=True)

        grammar = {
            "$schema": "https://raw.githubusercontent.com/martinring/tmlanguage/master/tmlanguage.json",
            "name": "Genesis YAML",
            "scopeName": "source.genesis.yaml",
            "fileTypes": ["genesis.yaml", "genesis.yml"],
            "patterns": [
                {"include": "#genesis-keywords"},
                {"include": "#genesis-component-types"},
                {"include": "#genesis-field-names"},
                {"include": "source.yaml"}
            ],
            "repository": {
                "genesis-keywords": {
                    "patterns": [
                        {
                            "name": "keyword.control.genesis",
                            "match": "\\b(id|name|description|agentGoal|kind|targetUser|valueGeneration|components|provides|useAs|asTools|config)\\b"
                        }
                    ]
                },
                "genesis-component-types": {
                    "patterns": [
                        {
                            "name": "entity.name.type.genesis",
                            "match": "\\bgenesis:(chat_input|chat_output|agent|crewai_agent|knowledge_hub_search|mcp_tool|api_request)\\b"
                        }
                    ]
                },
                "genesis-field-names": {
                    "patterns": [
                        {
                            "name": "variable.other.genesis",
                            "match": "\\b(provider|temperature|role|goal|backstory|tool_name|method|url_input)\\b"
                        }
                    ]
                }
            }
        }

        grammar_file = syntaxes_dir / "genesis.tmLanguage.json"
        with open(grammar_file, 'w') as f:
            json.dump(grammar, f, indent=2)

        return {str(grammar_file): json.dumps(grammar, indent=2)}

    def _generate_snippets(self, extension_path: Path) -> Dict[str, str]:
        """Generate code snippets for Genesis specifications."""
        snippets_dir = extension_path / "snippets"
        snippets_dir.mkdir(exist_ok=True)

        snippets = {
            "Genesis Specification Template": {
                "prefix": "genesis-spec",
                "body": [
                    "id: urn:agent:genesis:autonomize.ai:${1:spec-name}:1.0.0",
                    "name: ${2:Specification Name}",
                    "description: ${3:TODO: Add description}",
                    "agentGoal: ${4:TODO: Define agent goal}",
                    "kind: ${5|Single Agent,Multi Agent|}",
                    "targetUser: ${6|internal,external,customer|}",
                    "valueGeneration: ${7|ProcessAutomation,InsightGeneration,DecisionSupport|}",
                    "",
                    "components:",
                    "  input:",
                    "    type: genesis:chat_input",
                    "    name: User Input",
                    "    description: Receives user queries",
                    "    provides:",
                    "    - useAs: input",
                    "      in: agent",
                    "      description: User input to agent",
                    "",
                    "  agent:",
                    "    type: genesis:agent",
                    "    name: Main Agent",
                    "    description: Primary processing agent",
                    "    config:",
                    "      provider: Azure OpenAI",
                    "      temperature: 0.7",
                    "    provides:",
                    "    - useAs: response",
                    "      in: output",
                    "      description: Agent response to output",
                    "",
                    "  output:",
                    "    type: genesis:chat_output",
                    "    name: Response Output",
                    "    description: Displays the final response"
                ],
                "description": "Complete Genesis specification template"
            },
            "Genesis Agent Component": {
                "prefix": "genesis-agent",
                "body": [
                    "${1:agent_id}:",
                    "  type: genesis:agent",
                    "  name: ${2:Agent Name}",
                    "  description: ${3:Agent description}",
                    "  config:",
                    "    provider: ${4|Azure OpenAI,OpenAI,Anthropic|}",
                    "    temperature: ${5:0.7}",
                    "  provides:",
                    "  - useAs: ${6|response,input|}",
                    "    in: ${7:target_component}",
                    "    description: ${8:Connection description}"
                ],
                "description": "Genesis agent component"
            },
            "Genesis CrewAI Agent": {
                "prefix": "genesis-crewai-agent",
                "body": [
                    "${1:agent_id}:",
                    "  type: genesis:crewai_agent",
                    "  name: ${2:Agent Name}",
                    "  description: ${3:Agent description}",
                    "  config:",
                    "    role: ${4:Agent Role}",
                    "    goal: ${5:Agent Goal}",
                    "    backstory: ${6:Agent Backstory}"
                ],
                "description": "CrewAI agent component"
            },
            "Genesis Knowledge Search": {
                "prefix": "genesis-knowledge",
                "body": [
                    "${1:knowledge_id}:",
                    "  type: genesis:knowledge_hub_search",
                    "  name: ${2:Knowledge Search}",
                    "  description: ${3:Knowledge search description}",
                    "  asTools: true",
                    "  config:",
                    "    collections: [${4:\"collection1\", \"collection2\"}]",
                    "  provides:",
                    "  - useAs: tools",
                    "    in: ${5:agent_id}",
                    "    description: Knowledge search capability"
                ],
                "description": "Genesis knowledge search component"
            },
            "Genesis MCP Tool": {
                "prefix": "genesis-mcp",
                "body": [
                    "${1:tool_id}:",
                    "  type: genesis:mcp_tool",
                    "  name: ${2:MCP Tool}",
                    "  description: ${3:Tool description}",
                    "  asTools: true",
                    "  config:",
                    "    tool_name: ${4:tool_name}",
                    "  provides:",
                    "  - useAs: tools",
                    "    in: ${5:agent_id}",
                    "    description: ${6:Tool capability}"
                ],
                "description": "Genesis MCP tool component"
            },
            "Genesis API Request": {
                "prefix": "genesis-api",
                "body": [
                    "${1:api_id}:",
                    "  type: genesis:api_request",
                    "  name: ${2:API Request}",
                    "  description: ${3:API description}",
                    "  config:",
                    "    method: ${4|GET,POST,PUT,DELETE|}",
                    "    url_input: ${5:https://api.example.com/endpoint}",
                    "    headers:",
                    "    - key: Authorization",
                    "      value: Bearer \\${API_TOKEN}",
                    "  provides:",
                    "  - useAs: ${6|tools,input|}",
                    "    in: ${7:target_component}",
                    "    description: ${8:API connection}"
                ],
                "description": "Genesis API request component"
            }
        }

        snippets_file = snippets_dir / "genesis.json"
        with open(snippets_file, 'w') as f:
            json.dump(snippets, f, indent=2)

        return {str(snippets_file): json.dumps(snippets, indent=2)}

    def _generate_themes(self, extension_path: Path) -> Dict[str, str]:
        """Generate custom themes for Genesis specifications."""
        themes_dir = extension_path / "themes"
        themes_dir.mkdir(exist_ok=True)

        # Dark theme
        dark_theme = {
            "name": "Genesis Dark",
            "type": "dark",
            "colors": {
                "editor.background": "#1e1e1e",
                "editor.foreground": "#d4d4d4",
                "editorLineNumber.foreground": "#858585",
                "editor.selectionBackground": "#264f78"
            },
            "tokenColors": [
                {
                    "scope": "keyword.control.genesis",
                    "settings": {
                        "foreground": "#569cd6",
                        "fontStyle": "bold"
                    }
                },
                {
                    "scope": "entity.name.type.genesis",
                    "settings": {
                        "foreground": "#4ec9b0",
                        "fontStyle": "bold"
                    }
                },
                {
                    "scope": "variable.other.genesis",
                    "settings": {
                        "foreground": "#9cdcfe"
                    }
                }
            ]
        }

        dark_theme_file = themes_dir / "genesis-dark.json"
        with open(dark_theme_file, 'w') as f:
            json.dump(dark_theme, f, indent=2)

        # Light theme
        light_theme = {
            "name": "Genesis Light",
            "type": "light",
            "colors": {
                "editor.background": "#ffffff",
                "editor.foreground": "#000000",
                "editorLineNumber.foreground": "#237893",
                "editor.selectionBackground": "#add6ff"
            },
            "tokenColors": [
                {
                    "scope": "keyword.control.genesis",
                    "settings": {
                        "foreground": "#0000ff",
                        "fontStyle": "bold"
                    }
                },
                {
                    "scope": "entity.name.type.genesis",
                    "settings": {
                        "foreground": "#267f99",
                        "fontStyle": "bold"
                    }
                },
                {
                    "scope": "variable.other.genesis",
                    "settings": {
                        "foreground": "#001080"
                    }
                }
            ]
        }

        light_theme_file = themes_dir / "genesis-light.json"
        with open(light_theme_file, 'w') as f:
            json.dump(light_theme, f, indent=2)

        return {
            str(dark_theme_file): json.dumps(dark_theme, indent=2),
            str(light_theme_file): json.dumps(light_theme, indent=2)
        }

    def _generate_documentation(self, extension_path: Path) -> Dict[str, str]:
        """Generate documentation files for the extension."""
        readme_content = f"""# Genesis Specifications VS Code Extension

Advanced VS Code extension for Genesis AI agent specifications with comprehensive LSP integration and enhanced development experience.

## Features

### 🔍 Real-time Validation
- Comprehensive validation with detailed error messages
- Integration with Phase 1-3 enhanced validation system
- Runtime-specific validation support

### 💡 Intelligent Auto-completion
- Component type suggestions
- Field name completion
- Value suggestions based on context
- Snippet integration

### 🎨 Syntax Highlighting
- Custom syntax highlighting for Genesis YAML
- Color-coded component types and keywords
- Enhanced readability

### 🛠️ Developer Tools
- Format document command
- Convert to Langflow command
- Preview flow visualization
- Create new specification wizard

### 🎯 Language Server Protocol
- Real-time error reporting
- Hover documentation
- Code actions and quick fixes
- Diagnostic information

## Installation

1. Install from VS Code Marketplace: `{self.extension_id}`
2. Or install manually:
   ```bash
   cd {self.extension_name}
   npm install
   vsce package
   code --install-extension {self.extension_name}-1.0.0.vsix
   ```

## Configuration

Configure the extension through VS Code settings:

```json
{{
  "genesis.validation.enabled": true,
  "genesis.validation.mode": "comprehensive",
  "genesis.lsp.enabled": true,
  "genesis.lsp.port": 8080,
  "genesis.conversion.defaultRuntime": "langflow",
  "genesis.completion.enabled": true,
  "genesis.completion.includeSnippets": true
}}
```

## Usage

### Creating a New Specification

1. Right-click in the Explorer
2. Select "Create New Specification"
3. Enter specification name
4. Template will be created automatically

### Validating Specifications

- Validation runs automatically on file changes
- Use `Ctrl+Shift+V` (or `Cmd+Shift+V` on Mac) to validate manually
- Errors and warnings appear in the Problems panel

### Converting to Langflow

- Use `Ctrl+Shift+C` (or `Cmd+Shift+C` on Mac) to convert
- Or right-click and select "Convert to Langflow"

### Code Snippets

Type the following prefixes and press Tab:

- `genesis-spec` - Complete specification template
- `genesis-agent` - Agent component
- `genesis-crewai-agent` - CrewAI agent component
- `genesis-knowledge` - Knowledge search component
- `genesis-mcp` - MCP tool component
- `genesis-api` - API request component

## Language Server

The extension includes a Language Server Protocol implementation that provides:

- Real-time validation
- Auto-completion
- Hover documentation
- Error reporting
- Code actions

Start the language server manually if needed:
```bash
python -m langflow.services.ide.language_server 8080
```

## Commands

| Command | Keybinding | Description |
|---------|------------|-------------|
| `genesis.validate` | `Ctrl+Shift+V` | Validate specification |
| `genesis.convert` | `Ctrl+Shift+C` | Convert to Langflow |
| `genesis.create` | - | Create new specification |
| `genesis.preview` | - | Preview flow diagram |
| `genesis.format` | - | Format document |

## File Extensions

The extension recognizes these file patterns:
- `*.genesis.yaml`
- `*.genesis.yml`

## Themes

Two custom themes are included:
- Genesis Dark (dark theme)
- Genesis Light (light theme)

## Support

For issues and feature requests, please visit:
[GitHub Repository](https://github.com/autonomize-ai/genesis-vscode)

## License

MIT License - see LICENSE file for details.
"""

        readme_file = extension_path / "README.md"
        with open(readme_file, 'w') as f:
            f.write(readme_content)

        # Changelog
        changelog_content = """# Change Log

## [1.0.0] - 2025-01-16

### Added
- Initial release of Genesis Specifications extension
- Language Server Protocol support
- Real-time validation with Phase 1-3 integration
- Intelligent auto-completion
- Syntax highlighting for Genesis YAML
- Code snippets for common patterns
- Commands for validation and conversion
- Custom themes (Genesis Dark/Light)
- Preview functionality
- Documentation and hover support

### Features
- Comprehensive validation system
- Multi-runtime conversion support
- Performance optimization integration
- Developer-friendly tooling
- Enhanced error reporting
"""

        changelog_file = extension_path / "CHANGELOG.md"
        with open(changelog_file, 'w') as f:
            f.write(changelog_content)

        return {
            str(readme_file): readme_content,
            str(changelog_file): changelog_content
        }


def generate_vscode_extension(output_dir: str = "./vscode-extension") -> Dict[str, str]:
    """
    Generate VS Code extension for Genesis specifications.

    Args:
        output_dir: Output directory for extension files

    Returns:
        Dictionary mapping file paths to generated content
    """
    generator = VSCodeExtensionGenerator()
    return generator.generate_extension(output_dir)


if __name__ == "__main__":
    # Generate extension
    files = generate_vscode_extension()

    print("Generated VS Code extension files:")
    for file_path in files.keys():
        print(f"  - {file_path}")

    print(f"\nTotal files generated: {len(files)}")