import os
import platform
import subprocess
import threading
import time
import signal
import json
import psutil
from queue import Queue, Empty
from typing import Dict, Optional, Any, List
from pathlib import Path

from langflow.custom import Component
from langflow.field_typing import Tool
from langflow.io import StrInput, Output
from langchain_core.tools import tool

# --- Signal Mapping ---
SIGNAL_MAP = {
    "sigint": signal.SIGINT,   # Interrupt (like Ctrl+C)
    "sigterm": signal.SIGTERM, # Termination request (graceful shutdown)
    "sigkill": signal.SIGKILL, # Force kill (like kill -9)
}
# Add Windows-specific signals if applicable
if platform.system() == "Windows":
    # SIGBREAK is often used for console interrupts on Windows
    SIGNAL_MAP["sigbreak"] = signal.SIGBREAK
# --- End Signal Mapping ---


class ShellSessionManager(Component):
    display_name = "Shell Session Manager"
    description = (
        "Manages persistent interactive shell sessions, allowing commands "
        "to be run asynchronously and output/signals to be managed. "
        "Warning: Executing arbitrary shell commands can be dangerous. "
        "Note: Interactive shells often produce expected diagnostic output "
        "on STDERR which can usually be ignored."
    )
    icon = "Terminal"
    name = "ShellSessionManager"

    # File to store persistent session data
    SESSIONS_FILE = os.path.join(os.path.expanduser("~"), ".langflow_shell_sessions.json")

    inputs = [
        StrInput(
            name="working_directory",
            display_name="Working Directory",
            info=(
                "Optional base working directory for new shell sessions. "
                "Absolute paths are strongly recommended. Relative paths are resolved "
                "based on the Langflow process's CWD."
            ),
            required=False,
            value="",
        ),
        StrInput(
            name="default_shell",
            display_name="Default Shell",
            info=(
                "Optional path to the default shell executable (e.g., 'bash', "
                "'powershell', 'cmd.exe'). If not set, attempts auto-detection."
            ),
            required=False,
            value="",
        ),
        StrInput(
            name="sessions_directory",
            display_name="Sessions Directory",
            info=(
                "Optional directory to store session data. "
                "Defaults to ~/.langflow_shell_sessions/"
            ),
            required=False,
            value="",
        ),
    ]

    outputs = [
        Output(name="tools", display_name="Tools", method="build_toolkit"),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self._component_lock = threading.Lock()
        self._session_output_files = {}
        
        # Create sessions directory if it doesn't exist
        self.sessions_dir = self._get_sessions_directory()
        os.makedirs(self.sessions_dir, exist_ok=True)
        
        # Load any existing sessions
        self._load_sessions()

    def _get_sessions_directory(self) -> str:
        """Get the directory for storing session data."""
        if hasattr(self, "sessions_directory") and self.sessions_directory:
            directory = self.sessions_directory
        else:
            directory = os.path.join(os.path.expanduser("~"), ".langflow_shell_sessions")
        return directory

    def _get_session_file_path(self, session_id: str) -> str:
        """Get the path to a session's metadata file."""
        return os.path.join(self.sessions_dir, f"{session_id}.json")
    
    def _get_session_output_path(self, session_id: str) -> str:
        """Get the path to a session's output file."""
        return os.path.join(self.sessions_dir, f"{session_id}.log")

    def _detect_shell(self) -> str:
        system = platform.system()
        if system == "Windows":
            return os.environ.get("COMSPEC", "cmd.exe")
        return os.environ.get("SHELL", "/bin/sh")

    def _get_shell_command(self, shell_override: Optional[str] = None) -> list[str]:
        shell_executable = shell_override or self.default_shell or self._detect_shell()
        if "cmd.exe" in shell_executable.lower():
            return [shell_executable, "/K", "echo off"]
        elif "powershell" in shell_executable.lower():
            return [shell_executable, "-NoExit", "-Command", "-"]
        else:
            return [shell_executable, "-i"]

    def _read_stream(self, stream, queue: Queue, session_id: str, stream_name: str):
        try:
            # Open the output file for this session
            output_path = self._get_session_output_path(session_id)
            with open(output_path, "a", encoding="utf-8") as output_file:
                while stream and not stream.closed:
                    line = stream.readline()
                    if line:
                        # Write to both queue and file
                        queue.put(line)
                        output_file.write(line)
                        output_file.flush()
                    else:
                        break
        except ValueError:
             print(f"Info: Stream {stream_name} for session {session_id} already closed.")
        except Exception as e:
            print(f"Error reading {stream_name} for session {session_id}: {type(e).__name__}: {e}")
        finally:
            queue.put(None)

    def _save_session(self, session_id: str, session_data: dict):
        """Save session metadata to disk."""
        try:
            # Filter out non-serializable objects
            serializable_data = {
                "session_id": session_id,
                "shell_type": session_data.get("shell_type", ""),
                "working_dir": session_data.get("working_dir", ""),
                "pid": session_data["process"].pid if "process" in session_data else None,
                "start_time": time.time(),
            }
            
            # Save to a session-specific file
            session_file = self._get_session_file_path(session_id)
            with open(session_file, "w") as f:
                json.dump(serializable_data, f)
        except Exception as e:
            print(f"Error saving session {session_id} to disk: {e}")

    def _delete_session_file(self, session_id: str):
        """Delete session metadata file from disk."""
        try:
            session_file = self._get_session_file_path(session_id)
            if os.path.exists(session_file):
                os.remove(session_file)
                
            # Also try to delete output file if it exists
            output_file = self._get_session_output_path(session_id)
            if os.path.exists(output_file):
                os.remove(output_file)
        except Exception as e:
            print(f"Error deleting session file for {session_id}: {e}")

    def _load_sessions(self):
        """Load session data from disk and verify which sessions are still running."""
        try:
            # Look for all session files in the sessions directory
            session_files = [f for f in os.listdir(self.sessions_dir) if f.endswith('.json')]
            
            recovered = 0
            for session_file in session_files:
                try:
                    session_id = session_file.replace('.json', '')
                    file_path = os.path.join(self.sessions_dir, session_file)
                    
                    with open(file_path, 'r') as f:
                        session_data = json.load(f)
                    
                    # Check if the process is still running
                    pid = session_data.get('pid')
                    if pid and self._is_process_running(pid):
                        # Process is still running, recover the session
                        self._recover_session(session_id, session_data)
                        recovered += 1
                    else:
                        # Process is not running, clean up the session files
                        self._delete_session_file(session_id)
                except Exception as e:
                    print(f"Error loading session from {session_file}: {e}")
            
            if recovered > 0:
                print(f"Recovered {recovered} active shell sessions")
        except Exception as e:
            print(f"Error loading sessions: {e}")

    def _is_process_running(self, pid: int) -> bool:
        """Check if a process with the given PID is still running."""
        try:
            # Check if process exists and is not a zombie/defunct
            process = psutil.Process(pid)
            return process.is_running() and process.status() != psutil.STATUS_ZOMBIE
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return False
        except Exception as e:
            print(f"Error checking process {pid}: {e}")
            return False

    def _recover_session(self, session_id: str, session_data: dict):
        """Recover a running session by reconnecting to its process."""
        try:
            pid = session_data.get('pid')
            if not pid:
                print(f"Cannot recover session {session_id}: No PID found")
                return
                
            # Create new queues for stdout/stderr
            stdout_q, stderr_q = Queue(), Queue()
            
            # Create minimal session data that allows interaction
            shell_type = session_data.get('shell_type', self._detect_shell())
            working_dir = session_data.get('working_dir', os.getcwd())
            
            # Get the process object
            process = psutil.Process(pid)
            
            print(f"Recovering session {session_id} (PID: {pid}, Shell: {shell_type})")
            
            # Create a new session entry with minimal information needed
            with self._component_lock:
                self.sessions[session_id] = {
                    "process": process,
                    "stdout_q": stdout_q,
                    "stderr_q": stderr_q,
                    "stdout_thread": None,  # We don't have access to the original streams
                    "stderr_thread": None,
                    "shell_type": shell_type,
                    "working_dir": working_dir,
                    "lock": threading.Lock(),
                    "recovered": True,  # Mark as recovered
                }
        except Exception as e:
            print(f"Error recovering session {session_id}: {e}")
            # Clean up the session files since recovery failed
            self._delete_session_file(session_id)

    def _read_output_file(self, session_id: str, max_lines: int = 100) -> str:
        """Read recent output from the session's output file."""
        output_path = self._get_session_output_path(session_id)
        try:
            if not os.path.exists(output_path):
                return f"No output file found for session {session_id}"
                
            # Read the last max_lines from the output file
            with open(output_path, 'r', encoding='utf-8') as f:
                # Read all lines and get the last max_lines
                lines = f.readlines()
                if not lines:
                    return f"No output available for session {session_id}"
                    
                recent_lines = lines[-max_lines:] if max_lines > 0 else lines
                return "".join(recent_lines)
        except Exception as e:
            return f"Error reading output for session {session_id}: {e}"

    def build_toolkit(self) -> List[Tool]:
        """Builds and returns the shell session management tools."""

        @tool
        def start_shell_session(
            session_name: str = "", shell_override: Optional[str] = None, cwd: Optional[str] = None
        ) -> str:
            """Starts a new interactive shell session.

            Args:
                session_name (str): Custom name for the session (must not contain spaces). If empty, a name will be generated.
                shell_override (Optional[str]): Path to a specific shell executable.
                cwd (Optional[str]): Working directory. Absolute paths recommended.
                                     Relative paths resolved based on component/process CWD.

            Returns:
                str: Success message with session ID or an error message.
            """
            # Generate session ID based on input or create a default name
            if not session_name:
                session_name = f"shell_{int(time.time())}"
            elif " " in session_name:
                return f"Error: Session name '{session_name}' cannot contain spaces. Please provide a valid name."
            
            # First, check if we need to cleanup any stale sessions with this name
            with self._component_lock:
                if session_name in self.sessions:
                    # Check if the session is actually still running
                    process = self.sessions[session_name]["process"]
                    
                    # For recovered sessions, check differently
                    if self.sessions[session_name].get("recovered", False):
                        is_running = self._is_process_running(process.pid)
                    else:
                        is_running = process.poll() is None
                        
                    if not is_running:
                        # Process has terminated, clean up and reuse the name
                        print(f"Found stale session with name '{session_name}', cleaning up before reuse")
                        self._cleanup_session(session_name)
                    else:
                        # Session is still running
                        return f"Error: Session '{session_name}' already exists and is still running. Please choose a different name."
            
            print(f"Starting new session with name: {session_name}")
                        
            component_base_cwd = self.working_directory or None
            effective_base_cwd = os.getcwd()
            if component_base_cwd and os.path.isabs(component_base_cwd):
                effective_base_cwd = component_base_cwd

            resolved_cwd = cwd
            if resolved_cwd:
                if not os.path.isabs(resolved_cwd):
                    resolved_cwd = os.path.abspath(os.path.join(effective_base_cwd, resolved_cwd))
            elif component_base_cwd:
                if os.path.isabs(component_base_cwd):
                    resolved_cwd = component_base_cwd
                else:
                    resolved_cwd = os.path.abspath(os.path.join(effective_base_cwd, component_base_cwd))
            else:
                resolved_cwd = None

            if resolved_cwd and not os.path.isdir(resolved_cwd):
                 return f"Error: Resolved working directory '{resolved_cwd}' not found or not a directory."

            try:
                shell_cmd = self._get_shell_command(shell_override)
                shell_type = shell_cmd[0]
                print(f"Starting session {session_name}: Shell={shell_cmd}, CWD={resolved_cwd or 'Default'}")

                process = subprocess.Popen(
                    shell_cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, encoding='utf-8', errors='replace', cwd=resolved_cwd,
                    bufsize=1, universal_newlines=True, shell=False,
                    start_new_session=(platform.system() != "Windows")
                )
                stdout_q, stderr_q = Queue(), Queue()
                stdout_thread = threading.Thread(target=self._read_stream, args=(process.stdout, stdout_q, session_name, "stdout"), daemon=True)
                stderr_thread = threading.Thread(target=self._read_stream, args=(process.stderr, stderr_q, session_name, "stderr"), daemon=True)
                stdout_thread.start(); stderr_thread.start()

                with self._component_lock:
                    self.sessions[session_name] = {
                        "process": process, "stdout_q": stdout_q, "stderr_q": stderr_q,
                        "stdout_thread": stdout_thread, "stderr_thread": stderr_thread,
                        "shell_type": shell_type, "working_dir": resolved_cwd or os.getcwd(),
                        "lock": threading.Lock(),
                    }
                    
                # Save session data to disk for persistence
                self._save_session(session_name, self.sessions[session_name])
                
                return f"Session started with ID: {session_name}"
            except Exception as e:
                print(f"Error starting session {session_name}: {e}")
                return f"Error starting shell session: {str(e)}"

        @tool
        def run_command(session_id: str, command: str) -> str:
            """Sends a command to a running shell session asynchronously.

            Args:
                session_id (str): The ID of the target session.
                command (str): The command string to execute.

            Returns:
                str: Confirmation message or an error.
            """
            with self._component_lock:
                session = self.sessions.get(session_id)
            if not session: return f"Error: Session ID '{session_id}' not found."

            process = session["process"]
            
            # For recovered sessions, check process status differently
            if session.get("recovered", False):
                if not self._is_process_running(process.pid):
                    with self._component_lock:
                        if session_id in self.sessions:
                            print(f"Session {session_id} found terminated before running command, cleaning up.")
                            self._cleanup_session(session_id)
                    return f"Error: Session '{session_id}' appears to have terminated."
            else:
                # Standard case
                if process.poll() is not None:
                    with self._component_lock:
                        if session_id in self.sessions:
                            print(f"Session {session_id} found terminated before running command, cleaning up.")
                            self._cleanup_session(session_id)
                    return f"Error: Session '{session_id}' appears to have terminated."

            try:
                with session["lock"]:
                    # For recovered sessions, we need to reopen stdin
                    if session.get("recovered", False):
                        try:
                            # Use psutil to get process information
                            proc = psutil.Process(process.pid)
                            
                            # Try to send the command using OS-specific methods
                            if platform.system() == "Windows":
                                # On Windows, this is more complicated and may not work reliably
                                return f"Warning: Cannot send commands to recovered sessions on Windows. Please start a new session."
                            else:
                                # On Unix-like systems, we can try using the proc filesystem
                                newline = "\n"
                                if not command.endswith(newline): command += newline
                                
                                # Write to the log file
                                output_path = self._get_session_output_path(session_id)
                                with open(output_path, "a", encoding="utf-8") as output_file:
                                    output_file.write(f"COMMAND: {command}")
                                    output_file.flush()
                                
                                # Need to use os.write to a pipe or similar
                                return f"Warning: Sending command to recovered session {session_id} may not work. Command recorded in log."
                        except Exception as e:
                            print(f"Error sending command to recovered session {session_id}: {e}")
                            return f"Error sending command to recovered session {session_id}: {str(e)}"
                    
                    # Normal case - session we created
                    newline = "\r\n" if session["shell_type"].lower().endswith("cmd.exe") else "\n"
                    if not command.endswith(newline): command += newline
                    if not process.stdin or process.stdin.closed:
                         print(f"Error: Stdin for session {session_id} is closed. Cleaning up.")
                         with self._component_lock:
                              if session_id in self.sessions: self._cleanup_session(session_id)
                         return f"Error sending command: Stdin for session {session_id} is closed."

                    process.stdin.write(command)
                    process.stdin.flush()
                return f"Command sent to session {session_id}."
            except (IOError, OSError, BrokenPipeError) as e:
                print(f"Error writing to session {session_id}: {e}")
                with self._component_lock:
                    if session_id in self.sessions: self._cleanup_session(session_id)
                return f"Error sending command to session {session_id}: {str(e)}. Session may have terminated."
            except Exception as e:
                 print(f"Unexpected error sending command to {session_id}: {e}")
                 return f"Error sending command to session {session_id}: {str(e)}"

        @tool
        def get_session_output(session_id: str, read_all: bool = True, max_lines: int = 100) -> str:
            """Retrieves available stdout/stderr from a session since the last call.

            Args:
                session_id (str): The ID of the target session.
                read_all (bool): If True, reads all currently buffered output. Default True.
                max_lines (int): For recovered sessions, max number of lines to read from log file.

            Returns:
                str: Formatted output, status message, or error message.
            """
            with self._component_lock:
                 session = self.sessions.get(session_id)
            if not session: return f"Error: Session ID '{session_id}' not found."

            # For recovered sessions, read from the log file
            if session.get("recovered", False):
                output = self._read_output_file(session_id, max_lines)
                
                # Check if the process is still running
                if not self._is_process_running(session["process"].pid):
                    with self._component_lock:
                        if session_id in self.sessions:
                            self._cleanup_session(session_id)
                    return output + f"\n(Session '{session_id}' has terminated.)"
                return output

            # Standard case - read from queues
            stdout_lines, stderr_lines = [], []
            with session["lock"]:
                 stdout_q, stderr_q = session["stdout_q"], session["stderr_q"]
                 try:
                    while True:
                        line = stdout_q.get_nowait()
                        if line is None:
                             if session["stdout_thread"].is_alive(): session["stdout_thread"].join(timeout=0.5)
                             break
                        stdout_lines.append(line)
                        if not read_all: break
                 except Empty: pass
                 try:
                    while True:
                        line = stderr_q.get_nowait()
                        if line is None:
                            if session["stderr_thread"].is_alive(): session["stderr_thread"].join(timeout=0.5)
                            break
                        stderr_lines.append(line)
                        if not read_all: break
                 except Empty: pass

            output = ""
            if stdout_lines: output += "STDOUT:\n" + "".join(stdout_lines)
            if stderr_lines: output += "STDERR:\n" + "".join(stderr_lines)

            if not output:
                process = session["process"]
                if process.poll() is not None:
                    final_stdout, final_stderr = [], []
                    with session["lock"]:
                         try:
                              while True: line = stdout_q.get_nowait(); final_stdout.append(line) if line is not None else Ellipsis
                         except Empty: pass
                         try:
                              while True: line = stderr_q.get_nowait(); final_stderr.append(line) if line is not None else Ellipsis
                         except Empty: pass
                    if final_stdout: output += "STDOUT (final):\n" + "".join(final_stdout)
                    if final_stderr: output += "STDERR (final):\n" + "".join(final_stderr)

                    rc = process.returncode
                    msg = f"(Session '{session_id}' terminated with exit code: {rc})"
                    return (output.strip() + f"\n{msg}") if output else f"Session '{session_id}' terminated with exit code: {rc}. No final output."

                else:
                     return f"Session '{session_id}' has no new output available."
            return output.strip()

        @tool
        def list_shell_sessions() -> str:
            """Lists active shell sessions, cleaning up terminated ones found during check.

            Returns:
                str: Formatted list of active sessions or 'No active sessions.'
            """
            print(f"Listing sessions, current session dict has {len(self.sessions)} entries")
            
            # Scan the sessions directory first for any sessions we may have missed
            try:
                session_files = [f for f in os.listdir(self.sessions_dir) if f.endswith('.json')]
                for session_file in session_files:
                    session_id = session_file.replace('.json', '')
                    # If we don't have this session in memory, try to load it
                    if session_id not in self.sessions:
                        try:
                            file_path = os.path.join(self.sessions_dir, session_file)
                            with open(file_path, 'r') as f:
                                session_data = json.load(f)
                            
                            # Check if the process is still running
                            pid = session_data.get('pid')
                            if pid and self._is_process_running(pid):
                                # Process is still running, recover the session
                                self._recover_session(session_id, session_data)
                            else:
                                # Process is not running, clean up the session files
                                self._delete_session_file(session_id)
                        except Exception as e:
                            print(f"Error checking session file {session_file}: {e}")
            except Exception as e:
                print(f"Error scanning sessions directory: {e}")
            
            active_sessions_info = []
            terminated_sessions = []
            
            # First pass: collect status of all sessions
            for session_id, session in self.sessions.items():
                print(f"Checking session {session_id}")
                try:
                    process = session["process"]
                    
                    # Check if process is running
                    is_running = False
                    if session.get("recovered", False):
                        is_running = self._is_process_running(process.pid)
                    else:
                        is_running = process.poll() is None
                    
                    print(f"Session {session_id} running status: {is_running}")
                    
                    if is_running:
                        # Process is still running
                        active_sessions_info.append(f"  - ID: {session_id}, Shell: {session['shell_type']}, CWD: {session['working_dir']}")
                    else:
                        # Process has terminated, mark for cleanup
                        terminated_sessions.append(session_id)
                        print(f"Session {session_id} found terminated during listing")
                except Exception as e:
                    print(f"Error checking session {session_id}: {e}")
                    # If we can't check the session, assume it's terminated
                    terminated_sessions.append(session_id)
            
            # Second pass: clean up terminated sessions
            for session_id in terminated_sessions:
                try:
                    with self._component_lock:
                        if session_id in self.sessions:
                            print(f"Cleaning up terminated session {session_id}")
                            self._cleanup_session(session_id)
                except Exception as e:
                    print(f"Error cleaning up session {session_id}: {e}")
            
            # Return appropriate message based on active session count
            if active_sessions_info:
                return "Active Shell Sessions:\n" + "\n".join(active_sessions_info)
            else:
                return "No active sessions." if not terminated_sessions else "No active sessions found (all terminated sessions cleaned up)."

        @tool
        def send_signal_to_session(session_id: str, signal_name: str = "SIGINT") -> str:
            """Sends a signal (e.g., SIGINT for Ctrl+C, SIGKILL for kill -9)
               to the process running in the specified session.

            Args:
                session_id (str): The ID of the target session.
                signal_name (str): The name of the signal to send. Common values:
                                   'SIGINT' (default, like Ctrl+C),
                                   'SIGTERM' (graceful shutdown request),
                                   'SIGKILL' (forceful kill). Case-insensitive.
                                   On Windows, 'SIGBREAK' may also be useful.

            Returns:
                str: Confirmation message or an error.
            """
            normalized_signal_name = signal_name.lower()
            signal_to_send = SIGNAL_MAP.get(normalized_signal_name)

            if signal_to_send is None:
                supported_keys = list(SIGNAL_MAP.keys())
                if platform.system() != "Windows" and "sigbreak" in supported_keys:
                    supported_keys.remove("sigbreak")
                supported = ", ".join(supported_keys)
                return f"Error: Invalid signal name '{signal_name}'. Supported (case-insensitive): {supported}"

            with self._component_lock:
                session = self.sessions.get(session_id)
            if not session:
                return f"Error: Session ID '{session_id}' not found."

            process = session["process"]
            with session["lock"]:
                # Check if process is running
                is_running = False
                if session.get("recovered", False):
                    is_running = self._is_process_running(process.pid)
                    if not is_running:
                        return f"Error: Process in session '{session_id}' already terminated. Cannot send signal."
                else:
                    poll_result = process.poll()
                    if poll_result is not None:
                        return f"Error: Process in session '{session_id}' already terminated (exit code: {poll_result}). Cannot send signal."
                    is_running = True

                try:
                    pid_info = f"PID {process.pid}" if hasattr(process, 'pid') else "PID unknown"
                    print(f"Sending signal {normalized_signal_name} ({signal_to_send}) to process {pid_info} in session {session_id}")
                    
                    # For recovered sessions, use psutil
                    if session.get("recovered", False):
                        try:
                            psutil.Process(process.pid).send_signal(signal_to_send)
                        except psutil.NoSuchProcess:
                            return f"Error: Process {process.pid} in session '{session_id}' no longer exists."
                    else:
                        process.send_signal(signal_to_send)
                        
                    if signal_to_send == signal.SIGKILL:
                         time.sleep(0.05)
                         # Check status appropriately based on session type
                         if session.get("recovered", False):
                             final_status = not self._is_process_running(process.pid)
                         else:
                             final_poll = process.poll()
                             final_status = final_poll is not None
                             
                         status = "terminated" if final_status else "signal sent"
                         return f"Sent sigkill to process in session {session_id}. Process status: {status}."
                    else:
                         return f"Sent {normalized_signal_name} to process in session {session_id}."
                except Exception as e:
                    print(f"Error sending signal {normalized_signal_name} to session {session_id}: {type(e).__name__}: {e}")
                    
                    # Check current status
                    current_status = None
                    if session.get("recovered", False):
                        current_status = not self._is_process_running(process.pid)
                    else:
                        current_poll = process.poll()
                        current_status = current_poll is not None
                        
                    if current_status:
                         return f"Error sending signal {normalized_signal_name}: Process in session {session_id} terminated concurrently. Original error: {str(e)}"
                    else:
                         return f"Error sending signal {normalized_signal_name} to session {session_id}: {str(e)}"

        @tool
        def close_shell_session(session_id: str) -> str:
            """Closes a specific shell session and cleans up its resources.

            Args:
                session_id (str): The ID of the session to close.

            Returns:
                str: Confirmation message or an error.
            """
            with self._component_lock:
                if session_id not in self.sessions:
                    return f"Error: Session ID '{session_id}' not found."
                result = self._cleanup_session(session_id)
            return result

        return [
            start_shell_session,
            run_command,
            get_session_output,
            list_shell_sessions,
            send_signal_to_session,
            close_shell_session,
        ]

    def _cleanup_session(self, session_id: str) -> str:
        """Internal helper to clean up a session. Must be called holding _component_lock."""
        session = self.sessions.pop(session_id, None)
        if not session:
            print(f"Warning: Attempted cleanup of non-existent session {session_id}.")
            return f"Info: Session '{session_id}' already cleaned up or never existed."

        # Delete session file first
        self._delete_session_file(session_id)

        process = session["process"]
        shell_type = session["shell_type"]
        
        # For recovered sessions, we don't have direct access to threads
        if session.get("recovered", False):
            pid_info = f"PID {process.pid}" if hasattr(process, 'pid') else "PID unknown"
            print(f"Cleaning up recovered session {session_id} (Shell: {shell_type}, {pid_info})")
            
            try:
                # Check if the process is still running
                if self._is_process_running(process.pid):
                    try:
                        # Try to terminate the process
                        process.terminate() 
                        time.sleep(0.2)
                        
                        # If still running, try to kill
                        if self._is_process_running(process.pid):
                            process.kill()
                            time.sleep(0.2)
                    except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                        print(f"Error terminating recovered process: {e}")
                
                return f"Session {session_id} closed."
            except Exception as e:
                print(f"Error closing recovered session {session_id}: {e}")
                return f"Error closing session {session_id}: {str(e)}"
        
        # Standard case - session we created
        stdout_thread = session["stdout_thread"]
        stderr_thread = session["stderr_thread"]
        pid_info = f"PID {process.pid}" if hasattr(process, 'pid') else "PID unknown"
        print(f"Cleaning up session {session_id} (Shell: {shell_type}, {pid_info})")

        try:
            # Check if the process is still running before attempting interaction
            if process.poll() is None:
                try:
                    # Attempt graceful exit first
                    stdin_closed = getattr(process.stdin, 'closed', True)
                    if not stdin_closed:
                        try:
                            cmd = "exit\r\n" if shell_type.lower().endswith("cmd.exe") else "exit\n"
                            process.stdin.write(cmd); process.stdin.flush(); process.stdin.close()
                        except (BrokenPipeError, OSError, ValueError):
                            print(f"Session {session_id}: Info - Stdin likely closed before sending exit.")
                    # Wait briefly for graceful exit
                    process.wait(timeout=0.5)

                except subprocess.TimeoutExpired:
                    print(f"Session {session_id}: Graceful exit timed out, terminating.")
                    try:
                        process.terminate() # Send SIGTERM
                        process.wait(timeout=1) # Wait for termination
                    except subprocess.TimeoutExpired:
                        print(f"Session {session_id}: Termination timed out, killing.")
                        try:
                            process.kill() # Send SIGKILL
                            process.wait(timeout=1) # Wait for kill
                        except Exception as kill_wait_e:
                            print(f"Session {session_id}: Exc during kill wait: {kill_wait_e}")
                    except Exception as term_wait_e:
                         # Error during terminate/wait (e.g., process already dead)
                         print(f"Session {session_id}: Error during term/wait: {term_wait_e}. Attempting kill.")
                         # Check if still alive before kill - CORRECTED BLOCK
                         if process.poll() is None:
                              try:
                                   process.kill()
                                   process.wait(timeout=0.5)
                              except Exception as final_kill_e:
                                   print(f"Session {session_id}: Exception during final kill/wait after term error: {final_kill_e}")

                except (BrokenPipeError, OSError, ValueError) as e:
                     # Handle other potential errors during interaction (e.g., process died during wait)
                    print(f"Session {session_id}: Error during graceful exit attempt: {e}")
                    # Ensure kill if it's still running after the error - CORRECTED BLOCK
                    if process.poll() is None:
                        print(f"Session {session_id}: Killing process due to previous error.")
                        try:
                            process.kill()
                            process.wait(timeout=0.5)
                        except Exception as kill_wait_e:
                             print(f"Session {session_id}: Exception during final kill wait after IO error: {kill_wait_e}")

            # Process is confirmed or presumed terminated at this point
            return_code = process.poll() # Get final exit code if possible
            print(f"Session {session_id} process ended (Final code: {return_code}).")

            # Close streams safely
            for stream in [process.stdin, process.stdout, process.stderr]:
                 if stream and not stream.closed:
                    try: stream.close()
                    except (OSError, ValueError): pass # Ignore errors on already closed streams

            # Wait for reader threads
            for thread, name in [(stdout_thread, "stdout"), (stderr_thread, "stderr")]:
                if thread and thread.is_alive():
                    thread.join(timeout=0.5) # Wait a bit longer for threads
                    if thread.is_alive():
                        print(f"Warning: {name} thread for session {session_id} did not join cleanly.")

            return f"Session {session_id} closed."

        except Exception as e:
            # Catch-all for unexpected errors during cleanup
            print(f"Critical Error during cleanup of session {session_id}: {type(e).__name__}: {e}")
            return f"Error cleaning up session {session_id}: {str(e)}"

    def __del__(self):
        """Attempt to clean up any remaining sessions when the component instance is deleted."""
        print("ShellSessionManager deleting, cleaning up sessions...")
        with self._component_lock:
             session_ids = list(self.sessions.keys()) # Copy keys as cleanup modifies dict
             for session_id in session_ids:
                try:
                    # Call cleanup directly, it handles removing from self.sessions
                    self._cleanup_session(session_id)
                except Exception as e:
                    # Log error specific to the __del__ context
                    print(f"Error cleaning up session {session_id} during component deletion: {e}")
        print("ShellSessionManager cleanup finished.")
