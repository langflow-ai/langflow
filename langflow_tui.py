#!/usr/bin/env python3
"""
Langflow TUI - Interactive Terminal User Interface
A beautiful and interactive way to manage Langflow development tasks using Textual
With modern purple theme matching Langflow branding
"""

import subprocess
from typing import Optional

try:
    from textual.app import App, ComposeResult
    from textual.containers import Container, Horizontal
    from textual.widgets import (
        Header, Footer, Button, Static, Label, Input,
        OptionList, DataTable, Log, Markdown
    )
    from textual.binding import Binding
    from textual.screen import ModalScreen
    from textual import events
    from textual.reactive import reactive
    from textual.worker import Worker, WorkerState
except ImportError:
    print("Error: 'textual' library is required. Install it with:")
    print("  pip install textual")
    print("or")
    print("  uv pip install textual")
    import sys
    sys.exit(1)


# Langflow ASCII Art Logo - generated with oh-my-logo
# Generated using: render('LANGFLOW', { palette: 'purple', font: 'Standard' })
LANGFLOW_LOGO = r"""
[#FF3276]  _        _    _   _  ____ _____ _     _____        __[/]
[#7528FC] | |      / \  | \ | |/ ___|  ___| |   / _ \ \      / /[/]
[#FF3276] | |     / _ \ |  \| | |  _| |_  | |  | | | \ \ /\ / / [/]
[#7528FC] | |___ / ___ \| |\  | |_| |  _| | |__| |_| |\ V  V /  [/]
[#FF3276] |_____/_/   \_\_| \_|\____|_|   |_____\___/  \_/\_/   [/]

                  [dim]Interactive Development Interface[/]
"""

# Small version for headers - generated with oh-my-logo Small font
LANGFLOW_LOGO_SMALL = r"""
[#FF3276]  _      _   _  _  ___ ___ _    _____      __[/]
[#7528FC] | |    /_\ | \| |/ __| __| |  / _ \ \    / /[/]
[#FF3276] | |__ / _ \| .` | (_ | _|| |_| (_) \ \/\/ / [/]
[#7528FC] |____/_/ \_\_|\_|\___|_| |____\___/ \_/\_/  [/]
"""

# Welcome header (same as small logo)
WELCOME_HEADER = r"""
[#FF3276]  _      _   _  _  ___ ___ _    _____      __[/]
[#7528FC] | |    /_\ | \| |/ __| __| |  / _ \ \    / /[/]
[#FF3276] | |__ / _ \| .` | (_ | _|| |_| (_) \ \/\/ / [/]
[#7528FC] |____/_/ \_\_|\_|\___|_| |____\___/ \_/\_/  [/]

       [dim]Interactive Development Interface[/]
"""

WELCOME_TEXT = """
# Welcome! 🎉

This interactive interface helps you manage your Langflow development workflow with ease.

## Features:
- 🎯 **Interactive Commands**: Run make commands with guided inputs
- 📝 **Smart Prompts**: Get helpful hints for command variables
- 🎨 **Beautiful Interface**: Modern purple theme matching Langflow branding
- ⚡ **Quick Access**: Navigate through commands efficiently
- 📊 **Real-time Output**: Watch command execution live

## Navigation:
- Use **Tab** to navigate between elements
- Use **Arrow Keys** to select options
- Press **Enter** to confirm selections
- Press **Q** to quit or go back
- Press **Ctrl+C** to exit

## Quick Start:
1. Browse command categories in the left panel
2. Select a command from the right panel
3. Configure variables if needed
4. Execute and watch the output!

---
**Press any key to continue...**
"""

# Command definitions
COMMANDS = {
    "🚀 Getting Started": {
        "init": {
            "desc": "Initialize the project (install all dependencies)",
            "vars": {}
        },
        "setup_env": {
            "desc": "Set up environment variables",
            "vars": {}
        },
        "check_tools": {
            "desc": "Verify required tools are installed",
            "vars": {}
        }
    },
    "💻 Development": {
        "run_cli": {
            "desc": "Run Langflow CLI",
            "vars": {
                "port": {"default": "7860", "desc": "Port number"},
                "host": {"default": "0.0.0.0", "desc": "Host address"},
                "log_level": {"default": "debug", "desc": "Log level"},
                "open_browser": {"default": "true", "desc": "Open browser (true/false)"}
            }
        },
        "run_clic": {
            "desc": "Run CLI with fresh frontend build",
            "vars": {
                "port": {"default": "7860", "desc": "Port number"},
                "host": {"default": "0.0.0.0", "desc": "Host address"}
            }
        },
        "backend": {
            "desc": "Run backend in development mode",
            "vars": {
                "port": {"default": "7860", "desc": "Port number"},
                "workers": {"default": "1", "desc": "Number of workers"},
                "env": {"default": ".env", "desc": "Environment file"}
            }
        },
        "frontend": {
            "desc": "Run frontend in development mode",
            "vars": {}
        }
    },
    "🏗️ Build & Install": {
        "build": {
            "desc": "Build the project",
            "vars": {}
        },
        "build_frontend": {
            "desc": "Build frontend static files",
            "vars": {}
        },
        "install_backend": {
            "desc": "Install backend dependencies",
            "vars": {}
        },
        "install_frontend": {
            "desc": "Install frontend dependencies",
            "vars": {}
        }
    },
    "🧪 Testing": {
        "unit_tests": {
            "desc": "Run backend unit tests",
            "vars": {
                "async": {"default": "true", "desc": "Run tests async"},
                "lf": {"default": "false", "desc": "Run last failed"},
                "ff": {"default": "true", "desc": "Run failed first"}
            }
        },
        "integration_tests": {
            "desc": "Run integration tests",
            "vars": {}
        },
        "tests_frontend": {
            "desc": "Run frontend Playwright e2e tests",
            "vars": {
                "UI": {"default": "false", "desc": "Run with UI (true/false)"}
            }
        },
        "test_frontend": {
            "desc": "Run frontend Jest unit tests",
            "vars": {}
        }
    },
    "✨ Code Quality": {
        "format": {
            "desc": "Format all code (backend + frontend)",
            "vars": {}
        },
        "format_backend": {
            "desc": "Format backend code with ruff",
            "vars": {}
        },
        "format_frontend": {
            "desc": "Format frontend code",
            "vars": {}
        },
        "lint": {
            "desc": "Run backend linters (mypy)",
            "vars": {}
        },
        "codespell": {
            "desc": "Check spelling errors",
            "vars": {}
        }
    },
    "🧹 Cleanup": {
        "clean_all": {
            "desc": "Clean all caches and temporary directories",
            "vars": {}
        },
        "clean_python_cache": {
            "desc": "Clean Python cache files",
            "vars": {}
        },
        "clean_npm_cache": {
            "desc": "Clean npm cache and node_modules",
            "vars": {}
        },
        "clean_frontend_build": {
            "desc": "Clean frontend build artifacts",
            "vars": {}
        }
    },
    "🐳 Docker": {
        "docker_build": {
            "desc": "Build main Docker image",
            "vars": {}
        },
        "docker_compose_up": {
            "desc": "Build and start docker compose",
            "vars": {}
        },
        "docker_compose_down": {
            "desc": "Stop docker compose",
            "vars": {}
        }
    },
    "📚 Help Commands": {
        "help": {
            "desc": "Show basic commands overview",
            "vars": {}
        },
        "help_backend": {
            "desc": "Show backend-specific commands",
            "vars": {}
        },
        "help_frontend": {
            "desc": "Show frontend-specific commands",
            "vars": {}
        },
        "help_test": {
            "desc": "Show testing commands",
            "vars": {}
        },
        "help_docker": {
            "desc": "Show Docker commands",
            "vars": {}
        },
        "help_advanced": {
            "desc": "Show advanced commands",
            "vars": {}
        }
    }
}


class WelcomeScreen(ModalScreen[bool]):
    """Welcome screen shown on first launch with beautiful Langflow theme."""

    CSS = """
    WelcomeScreen {
        align: center middle;
    }

    WelcomeScreen > Container {
        width: 90;
        height: auto;
        border: heavy #7528FC;
        background: #0A0118;
        padding: 2;
    }

    WelcomeScreen .welcome-logo {
        text-align: center;
        color: #E9D5FF;
        padding: 1;
        margin-bottom: 1;
    }

    WelcomeScreen Markdown {
        height: auto;
        margin: 1 2;
        color: #E9D5FF;
    }

    WelcomeScreen Button {
        width: 100%;
        margin-top: 1;
        background: #7528FC;
        border: round #9333EA;
    }

    WelcomeScreen Button:hover {
        background: #9333EA;
    }
    """

    def compose(self) -> ComposeResult:
        with Container():
            yield Static(WELCOME_HEADER, classes="welcome-logo")
            yield Markdown(WELCOME_TEXT)
            yield Button("Let's Go! 🚀", variant="success", id="start")

    def on_button_pressed(self, _event: Button.Pressed) -> None:
        self.dismiss(True)

    def on_key(self, _event: events.Key) -> None:
        self.dismiss(True)


class VariableInputScreen(ModalScreen[Optional[dict[str, str]]]):
    """Modal screen for inputting command variables with Langflow theme."""

    CSS = """
    VariableInputScreen {
        align: center middle;
    }

    VariableInputScreen > Container {
        width: 80;
        height: auto;
        border: heavy #7528FC;
        background: #0A0118;
        padding: 2;
    }

    VariableInputScreen Static {
        color: #FF3276;
        margin-bottom: 1;
        text-style: bold;
    }

    VariableInputScreen Label {
        margin: 1 0;
        color: #E9D5FF;
    }

    VariableInputScreen Input {
        margin: 0 0 1 0;
        border: round #7528FC;
        background: #120828;
        color: #E9D5FF;
    }

    VariableInputScreen Input:focus {
        border: round #FF3276;
        background: #1A0E2E;
    }

    VariableInputScreen Horizontal {
        height: auto;
        margin-top: 1;
    }

    VariableInputScreen Button {
        width: 1fr;
        margin: 0 1;
    }
    """

    def __init__(self, command: str, variables: dict):
        super().__init__()
        self.command = command
        self.variables = variables
        self.input_values = {}

    def compose(self) -> ComposeResult:
        with Container():
            header_text = (
                f"[bold #FF3276]⚙️  Configure Variables[/]\n"
                f"[dim]Command:[/] [bold #7528FC]make {self.command}[/]"
            )
            yield Static(header_text, classes="title")
            yield Static("")

            for var_name, var_info in self.variables.items():
                label_text = f"[bold #7528FC]{var_name}[/] [dim]→[/] {var_info['desc']}"
                yield Label(label_text)
                yield Input(
                    placeholder=f"Default: {var_info['default']}",
                    value=var_info["default"],
                    id=f"input_{var_name}"
                )

            with Horizontal():
                yield Button("Execute ✓", variant="success", id="execute")
                yield Button("Cancel ✗", variant="error", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "execute":
            # Collect all input values
            for var_name in self.variables.keys():
                input_widget = self.query_one(f"#input_{var_name}", Input)
                self.input_values[var_name] = input_widget.value or self.variables[var_name]["default"]
            self.dismiss(self.input_values)
        else:
            self.dismiss(None)


class CommandOutput(Log):
    """Widget to display command output with real-time streaming."""

    DEFAULT_CSS = """
    CommandOutput {
        height: 1fr;
        border: round #FF3276;
        background: #0A0118;
        padding: 1;
        color: #E9D5FF;
        scrollbar-background: #0A0118;
        scrollbar-color: #FF3276;
    }
    """


class LangflowTUI(App):
    """Main Langflow TUI Application with modern Langflow-inspired theme."""

    CSS = """
    /* Langflow Brand Colors Theme */
    Screen {
        background: #0A0118;
    }

    Header {
        background: #7528FC;
        color: #FFFFFF;
        height: 3;
        text-style: bold;
    }

    .logo {
        color: #E9D5FF;
        text-align: center;
        padding: 1;
        background: #120828;
        border: round #7528FC;
        margin: 1;
    }

    #main-container {
        height: 1fr;
        layout: horizontal;
        margin: 1;
    }

    #categories {
        width: 32;
        height: 1fr;
        border: round #7528FC;
        background: #120828;
        padding: 1;
    }

    #categories Static {
        color: #FF3276;
        margin-bottom: 1;
        text-style: bold;
    }

    #commands-container {
        width: 1fr;
        height: 1fr;
        layout: vertical;
        margin-left: 1;
    }

    #commands {
        height: 50%;
        border: round #9333EA;
        background: #120828;
        padding: 1;
    }

    #commands Static {
        color: #FF3276;
        margin-bottom: 1;
        text-style: bold;
    }

    #output {
        height: 50%;
        margin-top: 1;
    }

    OptionList {
        height: 1fr;
        background: #120828;
        color: #E9D5FF;
        scrollbar-background: #0A0118;
        scrollbar-color: #7528FC;
    }

    OptionList > .option-list--option {
        color: #E9D5FF;
        padding: 0 1;
    }

    OptionList > .option-list--option-hover {
        background: #7528FC;
        color: #FFFFFF;
        text-style: bold;
    }

    OptionList > .option-list--option-highlighted {
        background: #9333EA;
        color: #FFFFFF;
        text-style: bold;
    }

    DataTable {
        height: 1fr;
        background: #120828;
        color: #E9D5FF;
        scrollbar-background: #0A0118;
        scrollbar-color: #7528FC;
    }

    DataTable > .datatable--header {
        background: #7528FC;
        color: #FFFFFF;
        text-style: bold;
    }

    DataTable > .datatable--cursor {
        background: #9333EA;
        color: #FFFFFF;
    }

    DataTable > .datatable--hover {
        background: #1A0E2E;
    }

    Button {
        margin: 1;
    }

    Button.-success {
        background: #7528FC;
        color: white;
        border: round #9333EA;
        text-style: bold;
    }

    Button.-success:hover {
        background: #9333EA;
        color: white;
    }

    Button.-error {
        background: #DC2626;
        color: white;
        border: solid #EF4444;
        text-style: bold;
    }

    Button.-error:hover {
        background: #EF4444;
    }

    #status-bar {
        background: #7528FC;
        color: #FFFFFF;
        height: 1;
        padding: 0 2;
        text-align: center;
        text-style: bold;
    }

    Footer {
        background: #1A0E2E;
        color: #E9D5FF;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("r", "refresh", "Refresh", show=True),
        Binding("h", "show_help", "Help", show=True),
        Binding("c", "cancel_command", "Cancel", show=True),
    ]

    TITLE = "Langflow Development TUI"

    selected_category: reactive[Optional[str]] = reactive(None)
    selected_command: reactive[Optional[str]] = reactive(None)
    running_process: subprocess.Popen | None = None
    is_running: reactive[bool] = reactive(False)

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header(show_clock=True)

        # Logo
        yield Static(LANGFLOW_LOGO, classes="logo")

        # Main container
        with Container(id="main-container"):
            # Left panel - Categories
            with Container(id="categories"):
                yield Static("[bold]📋 Command Categories[/]")
                yield OptionList(*list(COMMANDS.keys()), id="category-list")

            # Right panel - Commands and Output
            with Container(id="commands-container"):
                # Commands table
                with Container(id="commands"):
                    yield Static("[bold]⚡ Available Commands[/]")
                    table = DataTable(id="command-table", cursor_type="row")
                    table.add_columns("Command", "Description", "Vars")
                    yield table

                # Output log
                yield CommandOutput(id="output")

        # Status bar
        yield Static("Ready | Select a category to begin", id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        """Called when app is mounted."""
        # Show welcome screen
        self.push_screen(WelcomeScreen(), self.on_welcome_complete)

    def on_welcome_complete(self, _result: bool) -> None:
        """Called when welcome screen is dismissed."""
        self.query_one("#status-bar", Static).update(
            "Welcome! Select a category from the left panel to start."
        )

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle category selection."""
        category = str(event.option.prompt)
        self.selected_category = category
        self.update_commands_table(category)
        self.query_one("#status-bar", Static).update(
            f"Category: {category} | Select a command to execute"
        )

    def update_commands_table(self, category: str) -> None:
        """Update the commands table based on selected category."""
        table = self.query_one("#command-table", DataTable)
        table.clear()

        if category not in COMMANDS:
            return

        commands = COMMANDS[category]
        for cmd, info in commands.items():
            var_count = len(info["vars"])
            var_indicator = f"⚙️ {var_count}" if var_count > 0 else "—"
            table.add_row(
                f"make {cmd}",
                info["desc"][:50],
                var_indicator
            )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle command selection from table - execute on click."""
        if self.selected_category is None:
            return

        table = self.query_one("#command-table", DataTable)
        row_key = event.row_key
        row = table.get_row(row_key)
        command_text = str(row[0])
        command = command_text.replace("make ", "")

        # Get command info
        commands = COMMANDS[self.selected_category]
        if command not in commands:
            return

        cmd_info = commands[command]

        # Check if command has variables
        if cmd_info["vars"]:
            def on_variables_input(result: dict[str, str] | None) -> None:
                if result:
                    self.run_worker(
                        self.execute_command,
                        command=command,
                        variables=result,
                        thread=True,
                        exclusive=True
                    )

            self.push_screen(VariableInputScreen(command, cmd_info["vars"]), on_variables_input)
        else:
            # Execute immediately if no variables
            self.run_worker(
                self.execute_command,
                command=command,
                variables={},
                thread=True,
                exclusive=True
            )

    def execute_command(self, command: str, variables: dict[str, str]) -> None:
        """Execute a make command with real-time output streaming."""
        # Build command
        make_cmd = f"make {command}"
        if variables:
            var_parts = [f"{k}={v}" for k, v in variables.items() if v]
            if var_parts:
                make_cmd += " " + " ".join(var_parts)

        # Set running state
        self.is_running = True

        # Get output widget reference
        output = self.query_one("#output", CommandOutput)

        # Update status with running indicator
        self.call_from_thread(
            self.query_one("#status-bar", Static).update,
            f"[bold #FF3276]⚡ Executing:[/] [bold]{make_cmd}[/] [dim](Press C to cancel)[/]"
        )

        # Clear output and show header
        self.call_from_thread(output.clear)
        self.call_from_thread(output.write_line, "╭" + "─" * 78 + "╮")
        self.call_from_thread(
            output.write_line,
            f"│ [bold #FF3276]COMMAND:[/] [bold #7528FC]{make_cmd}[/]"
        )
        self.call_from_thread(output.write_line, "╰" + "─" * 78 + "╯")
        self.call_from_thread(output.write_line, "")

        # Execute command with real-time streaming
        try:
            # Note: preexec_fn is used intentionally to create process groups for proper cancellation
            # shell=True is required for make command compatibility
            self.running_process = subprocess.Popen(
                make_cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=0,  # Unbuffered for real-time output
                universal_newlines=True,
                preexec_fn=None if subprocess.os.name == "nt" else subprocess.os.setsid  # noqa: PLW1509
            )

            # Stream output in real-time
            line_count = 0
            while True:
                # Check if process was cancelled
                if self.running_process is None:
                    self.call_from_thread(output.write_line, "")
                    self.call_from_thread(output.write_line, "[bold #FCD34D]⚠ CANCELLED BY USER[/]")
                    self.call_from_thread(
                        self.query_one("#status-bar", Static).update,
                        "[bold #FCD34D]⚠ Cancelled[/] Command was cancelled by user"
                    )
                    self.call_from_thread(self.notify, "Command cancelled", severity="warning", timeout=3)
                    self.is_running = False
                    return

                line = self.running_process.stdout.readline()
                if not line and self.running_process.poll() is not None:
                    break

                if line:
                    line_count += 1
                    # Color output based on content
                    stripped = line.rstrip()
                    lower_line = stripped.lower()
                    if "error" in lower_line or "failed" in lower_line:
                        self.call_from_thread(output.write_line, f"[#EF4444]{stripped}[/]")
                    elif "warning" in lower_line:
                        self.call_from_thread(output.write_line, f"[#FCD34D]{stripped}[/]")
                    elif "success" in lower_line or "passed" in lower_line:
                        self.call_from_thread(output.write_line, f"[#10B981]{stripped}[/]")
                    elif stripped.startswith(("===", "---")):
                        self.call_from_thread(output.write_line, f"[#7528FC]{stripped}[/]")
                    else:
                        self.call_from_thread(output.write_line, f"[#E9D5FF]{stripped}[/]")

                    # Update status with line count and cancel hint
                    status_msg = (
                        f"[bold #FF3276]⚡ Running...[/] {line_count} lines | "
                        f"[dim]{make_cmd}[/] [bold #FCD34D](Press C to cancel)[/]"
                    )
                    self.call_from_thread(
                        self.query_one("#status-bar", Static).update,
                        status_msg
                    )

            self.running_process.wait()
            return_code = self.running_process.returncode
            self.running_process = None
            self.is_running = False

            # Show completion status
            self.call_from_thread(output.write_line, "")
            self.call_from_thread(output.write_line, "╭" + "─" * 78 + "╮")
            if return_code == 0:
                self.call_from_thread(
                    output.write_line,
                    f"│ [bold #10B981]✓ COMPLETED SUCCESSFULLY[/] [dim]({line_count!s} lines)[/]"
                )
                self.call_from_thread(output.write_line, "╰" + "─" * 78 + "╯")
                self.call_from_thread(
                    self.query_one("#status-bar", Static).update,
                    f"[bold #10B981]✓ Success![/] {make_cmd} completed successfully"
                )
                self.call_from_thread(
                    self.notify,
                    f"✓ {command} completed successfully",
                    severity="information",
                    timeout=3
                )
            else:
                self.call_from_thread(
                    output.write_line,
                    f"│ [bold #EF4444]✗ FAILED[/] [dim](exit code: {return_code!s})[/]"
                )
                self.call_from_thread(output.write_line, "╰" + "─" * 78 + "╯")
                self.call_from_thread(
                    self.query_one("#status-bar", Static).update,
                    f"[bold #EF4444]✗ Failed![/] Exit code: {return_code}"
                )
                error_msg = f"✗ {command} failed (exit code: {return_code})"
                self.call_from_thread(self.notify, error_msg, severity="error", timeout=5)

        except (subprocess.SubprocessError, OSError) as e:
            self.call_from_thread(output.write_line, "")
            self.call_from_thread(output.write_line, f"[bold #EF4444]✗ ERROR: {e!s}[/]")
            self.call_from_thread(
                self.query_one("#status-bar", Static).update,
                "[bold #EF4444]✗ Error![/] Command execution failed"
            )
            self.call_from_thread(
                self.notify,
                f"Error executing {command}: {e!s}",
                severity="error",
                timeout=5
            )
        finally:
            self.running_process = None
            self.is_running = False

    def action_cancel_command(self) -> None:
        """Cancel the currently running command."""
        if self.running_process and self.is_running:
            import signal
            try:
                # Try to terminate gracefully first
                if subprocess.os.name == "nt":
                    self.running_process.terminate()
                else:
                    # On Unix, kill the entire process group
                    subprocess.os.killpg(subprocess.os.getpgid(self.running_process.pid), signal.SIGTERM)

                # Wait a bit for graceful termination
                import time
                time.sleep(0.5)

                # If still running, force kill
                if self.running_process.poll() is None:
                    if subprocess.os.name == "nt":
                        self.running_process.kill()
                    else:
                        subprocess.os.killpg(subprocess.os.getpgid(self.running_process.pid), signal.SIGKILL)

                self.running_process = None
                self.is_running = False
                self.notify("Command cancelled", severity="warning", timeout=3)
            except ProcessLookupError as e:
                self.notify(f"Error cancelling command: {e!s}", severity="error", timeout=3)
        else:
            self.notify("No command is currently running", severity="information", timeout=2)

    def action_show_help(self) -> None:
        """Show help information."""
        help_msg = (
            "Tab: Navigate | Enter: Select | Q: Quit | "
            "C: Cancel running command | R: Refresh | H: Help"
        )
        self.notify(help_msg, severity="information", timeout=5)

    def action_refresh(self) -> None:
        """Refresh the display."""
        if self.selected_category:
            self.update_commands_table(self.selected_category)
        self.notify("Display refreshed", severity="information")


def main():
    """Run the Langflow TUI application."""
    app = LangflowTUI()
    app.run()


if __name__ == "__main__":
    main()
