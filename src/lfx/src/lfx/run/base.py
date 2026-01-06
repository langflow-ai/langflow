"""Core run functionality for executing Langflow graphs."""

import json
import re
import sys
import time
from io import StringIO
from pathlib import Path

from lfx.cli.script_loader import (
    extract_structured_result,
    extract_text_from_result,
    find_graph_variable,
    load_graph_from_script,
)
from lfx.cli.validation import validate_global_variables_for_env
from lfx.log.logger import logger
from lfx.schema.schema import InputValueRequest

# Verbosity level constants
VERBOSITY_DETAILED = 2
VERBOSITY_FULL = 3


class RunError(Exception):
    """Exception raised when run execution fails."""

    def __init__(self, message: str, exception: Exception | None = None):
        super().__init__(message)
        self.original_exception = exception


def output_error(error_message: str, *, verbose: bool, exception: Exception | None = None) -> dict:
    """Create error response dict and optionally print to stderr when verbose."""
    if verbose:
        sys.stderr.write(f"{error_message}\n")

    error_response = {
        "success": False,
        "type": "error",
    }

    # Add clean exception data if available
    if exception:
        error_response["exception_type"] = type(exception).__name__
        error_response["exception_message"] = str(exception)
    else:
        error_response["exception_message"] = error_message

    return error_response


async def run_flow(
    script_path: Path | None = None,
    input_value: str | None = None,
    input_value_option: str | None = None,
    output_format: str = "json",
    flow_json: str | None = None,
    *,
    stdin: bool = False,
    check_variables: bool = True,
    verbose: bool = False,
    verbose_detailed: bool = False,
    verbose_full: bool = False,
    timing: bool = False,
    global_variables: dict[str, str] | None = None,
) -> dict:
    """Execute a Langflow graph script or JSON flow and return the result.

    This function analyzes and executes either a Python script containing a Langflow graph,
    a JSON flow file, inline JSON, or JSON from stdin, returning the result as a dict.

    Args:
        script_path: Path to the Python script (.py) or JSON flow (.json) containing a graph
        input_value: Input value to pass to the graph (positional argument)
        input_value_option: Input value to pass to the graph (alternative option)
        output_format: Format for output (json, text, message, or result)
        flow_json: Inline JSON flow content as a string
        stdin: Read JSON flow content from stdin
        check_variables: Check global variables for environment compatibility
        verbose: Show basic progress information
        verbose_detailed: Show detailed progress and debug information
        verbose_full: Show full debugging output including component logs
        timing: Include detailed timing information in output
        global_variables: Dict of global variables to inject into the graph context

    Returns:
        dict: Result data containing the execution results, logs, and optionally timing info

    Raises:
        RunError: If execution fails at any stage
    """
    # Configure logger based on verbosity level
    from lfx.log.logger import configure

    if verbose_full:
        configure(log_level="DEBUG", output_file=sys.stderr)
        verbosity = 3
    elif verbose_detailed:
        configure(log_level="DEBUG", output_file=sys.stderr)
        verbosity = 2
    elif verbose:
        configure(log_level="INFO", output_file=sys.stderr)
        verbosity = 1
    else:
        configure(log_level="CRITICAL", output_file=sys.stderr)
        verbosity = 0

    start_time = time.time() if timing else None

    # Use either positional input_value or --input-value option
    final_input_value = input_value or input_value_option

    # Validate input sources - exactly one must be provided
    input_sources = [script_path is not None, flow_json is not None, bool(stdin)]
    if sum(input_sources) != 1:
        if sum(input_sources) == 0:
            error_msg = "No input source provided. Must provide either script_path, --flow-json, or --stdin"
        else:
            error_msg = (
                "Multiple input sources provided. Cannot use script_path, --flow-json, and "
                "--stdin together. Choose exactly one."
            )
        output_error(error_msg, verbose=verbose)
        raise RunError(error_msg, None)

    # Store parsed JSON dict for direct loading (avoids temp file round-trip)
    flow_dict: dict | None = None

    if flow_json is not None:
        if verbosity > 0:
            sys.stderr.write("Processing inline JSON content...\n")
        try:
            flow_dict = json.loads(flow_json)
            if verbosity > 0:
                sys.stderr.write("JSON content is valid\n")
        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON content: {e}"
            output_error(error_msg, verbose=verbose)
            raise RunError(error_msg, e) from e
        except Exception as e:
            error_msg = f"Error processing JSON content: {e}"
            output_error(error_msg, verbose=verbose)
            raise RunError(error_msg, e) from e
    elif stdin:
        if verbosity > 0:
            sys.stderr.write("Reading JSON content from stdin...\n")
        try:
            stdin_content = sys.stdin.read().strip()
            if not stdin_content:
                error_msg = "No content received from stdin"
                output_error(error_msg, verbose=verbose)
                raise RunError(error_msg, None)
            flow_dict = json.loads(stdin_content)
            if verbosity > 0:
                sys.stderr.write("JSON content from stdin is valid\n")
        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON content from stdin: {e}"
            output_error(error_msg, verbose=verbose)
            raise RunError(error_msg, e) from e
        except Exception as e:
            error_msg = f"Error reading from stdin: {e}"
            output_error(error_msg, verbose=verbose)
            raise RunError(error_msg, e) from e

    try:
        # Handle direct JSON dict (from stdin or --flow-json)
        if flow_dict is not None:
            if verbosity > 0:
                sys.stderr.write("Loading graph from JSON content...\n")
            from lfx.load import aload_flow_from_json

            graph = await aload_flow_from_json(flow_dict, disable_logs=not verbose)
        # Handle file path
        elif script_path is not None:
            if not script_path.exists():
                error_msg = f"File '{script_path}' does not exist."
                raise ValueError(error_msg)
            if not script_path.is_file():
                error_msg = f"'{script_path}' is not a file."
                raise ValueError(error_msg)
            file_extension = script_path.suffix.lower()
            if file_extension not in [".py", ".json"]:
                error_msg = f"'{script_path}' must be a .py or .json file."
                raise ValueError(error_msg)
            file_type = "Python script" if file_extension == ".py" else "JSON flow"
            if verbosity > 0:
                sys.stderr.write(f"Analyzing {file_type}: {script_path}\n")
            if file_extension == ".py":
                graph_info = find_graph_variable(script_path)
                if not graph_info:
                    error_msg = (
                        "No 'graph' variable found in the script. "
                        "Expected to find an assignment like: graph = Graph(...)"
                    )
                    raise ValueError(error_msg)
                if verbosity > 0:
                    sys.stderr.write(f"Found 'graph' variable at line {graph_info['line_number']}\n")
                    sys.stderr.write(f"Type: {graph_info['type']}\n")
                    sys.stderr.write(f"Source: {graph_info['source_line']}\n")
                    sys.stderr.write("Loading and executing script...\n")
                graph = await load_graph_from_script(script_path)
            else:  # .json file
                if verbosity > 0:
                    sys.stderr.write("Valid JSON flow file detected\n")
                    sys.stderr.write("Loading and executing JSON flow\n")
                from lfx.load import aload_flow_from_json

                graph = await aload_flow_from_json(script_path, disable_logs=not verbose)
        else:
            error_msg = "No input source provided"
            raise ValueError(error_msg)

        # Inject global variables into graph context
        if global_variables:
            if "request_variables" not in graph.context:
                graph.context["request_variables"] = {}
            graph.context["request_variables"].update(global_variables)
            if verbosity > 0:
                # Log keys only to avoid leaking sensitive data
                logger.info(f"Injected global variables: {list(global_variables.keys())}")

    except Exception as e:
        error_type = type(e).__name__
        logger.error(f"Graph loading failed with {error_type}")

        if verbosity > 0:
            # Try to identify common error patterns
            if "ModuleNotFoundError" in str(e) or "No module named" in str(e):
                logger.info("This appears to be a missing dependency issue")
                if "langchain" in str(e).lower():
                    match = re.search(r"langchain_(.*)", str(e).lower())
                    if match:
                        module_name = match.group(1)
                        logger.info(
                            f"Missing LangChain dependency detected. Try: pip install langchain-{module_name}",
                        )
            elif "ImportError" in str(e):
                logger.info("This appears to be an import issue - check component dependencies")
            elif "AttributeError" in str(e):
                logger.info("This appears to be a component configuration issue")

            # Show full traceback in debug mode
            logger.exception("Failed to load graph.")

        error_msg = f"Failed to load graph. {e}"
        output_error(error_msg, verbose=verbose, exception=e)
        raise RunError(error_msg, e) from e

    inputs = InputValueRequest(input_value=final_input_value) if final_input_value else None

    # Mark end of loading phase if timing
    load_end_time = time.time() if timing else None

    if verbosity > 0:
        sys.stderr.write("Preparing graph for execution...\n")
    try:
        # Add detailed preparation steps
        if verbosity > 0:
            logger.debug(f"Graph contains {len(graph.vertices)} vertices")
            logger.debug(f"Graph contains {len(graph.edges)} edges")

            # Show component types being used
            component_types = set()
            for vertex in graph.vertices:
                if hasattr(vertex, "display_name"):
                    component_types.add(vertex.display_name)
            logger.debug(f"Component types in graph: {', '.join(sorted(component_types))}")

        graph.prepare()
        logger.info("Graph preparation completed")

        # Validate global variables for environment compatibility
        if check_variables:
            logger.info("Validating global variables...")
            validation_errors = validate_global_variables_for_env(graph)
            if validation_errors:
                error_details = "Global variable validation failed: " + "; ".join(validation_errors)
                logger.info(f"Variable validation failed: {len(validation_errors)} errors")
                for error in validation_errors:
                    logger.debug(f"Validation error: {error}")
                output_error(error_details, verbose=verbose)
                raise RunError(error_details, None)
            logger.info("Global variable validation passed")
        else:
            logger.info("Global variable validation skipped")
    except RunError:
        raise
    except Exception as e:
        error_type = type(e).__name__
        logger.info(f"Graph preparation failed with {error_type}")

        if verbosity > 0:
            logger.debug(f"Preparation error: {e!s}")
            logger.exception("Failed to prepare graph - full traceback:")

        error_msg = f"Failed to prepare graph: {e}"
        output_error(error_msg, verbose=verbose, exception=e)
        raise RunError(error_msg, e) from e

    logger.info("Executing graph...")
    execution_start_time = time.time() if timing else None
    if verbose:
        logger.debug("Setting up execution environment")
        if inputs:
            logger.debug(f"Input provided: {inputs.input_value}")
        else:
            logger.debug("No input provided")

    captured_stdout = StringIO()
    captured_stderr = StringIO()
    original_stdout = sys.stdout
    original_stderr = sys.stderr

    # Track component timing if requested
    component_timings = [] if timing else None
    execution_step_start = execution_start_time if timing else None
    result_count = 0

    try:
        sys.stdout = captured_stdout
        # Don't capture stderr at high verbosity levels to avoid duplication with direct logging
        if verbosity < VERBOSITY_FULL:
            sys.stderr = captured_stderr
        results = []

        logger.info("Starting graph execution...", level="DEBUG")

        async for result in graph.async_start(inputs):
            result_count += 1
            if verbosity > 0:
                logger.debug(f"Processing result #{result_count}")
                if hasattr(result, "vertex") and hasattr(result.vertex, "display_name"):
                    logger.debug(f"Component: {result.vertex.display_name}")
            if timing:
                step_end_time = time.time()
                step_duration = step_end_time - execution_step_start

                # Extract component information
                if hasattr(result, "vertex"):
                    component_name = getattr(result.vertex, "display_name", "Unknown")
                    component_id = getattr(result.vertex, "id", "Unknown")
                    component_timings.append(
                        {
                            "component": component_name,
                            "component_id": component_id,
                            "duration": step_duration,
                            "cumulative_time": step_end_time - execution_start_time,
                        }
                    )

                execution_step_start = step_end_time

            results.append(result)

        logger.info(f"Graph execution completed. Processed {result_count} results")

    except Exception as e:
        error_type = type(e).__name__
        logger.info(f"Graph execution failed with {error_type}")

        if verbosity >= VERBOSITY_DETAILED:  # Only show details at -vv and above
            logger.debug(f"Failed after processing {result_count} results")

        # Only show component output at maximum verbosity (-vvv)
        if verbosity >= VERBOSITY_FULL:
            # Capture any output that was generated before the error
            # Only show captured stdout since stderr logging is already shown directly in verbose mode
            captured_content = captured_stdout.getvalue()
            if captured_content.strip():
                # Check if captured content contains the same error that will be displayed at the end
                error_text = str(e)
                captured_lines = captured_content.strip().split("\n")

                # Filter out lines that are duplicates of the final error message
                unique_lines = [
                    line
                    for line in captured_lines
                    if not any(
                        error_part.strip() in line for error_part in error_text.split("\n") if error_part.strip()
                    )
                ]

                if unique_lines:
                    logger.info("Component output before error:", level="DEBUG")
                    for line in unique_lines:
                        # Log each line directly using the logger to avoid nested formatting
                        if verbosity > 0:
                            # Remove any existing timestamp prefix to avoid duplication
                            clean_line = line
                            if "] " in line and line.startswith("2025-"):
                                # Extract just the log message after the timestamp and level
                                parts = line.split("] ", 1)
                                if len(parts) > 1:
                                    clean_line = parts[1]
                            logger.debug(clean_line)

            # Provide context about common execution errors
            if "list can't be used in 'await' expression" in str(e):
                logger.info("This appears to be an async/await mismatch in a component")
                logger.info("Check that async methods are properly awaited")
            elif "AttributeError" in error_type and "NoneType" in str(e):
                logger.info("This appears to be a null reference error")
                logger.info("A component may be receiving unexpected None values")
            elif "ConnectionError" in str(e) or "TimeoutError" in str(e):
                logger.info("This appears to be a network connectivity issue")
                logger.info("Check API keys and network connectivity")

            logger.exception("Failed to execute graph - full traceback:")

        sys.stdout = original_stdout
        sys.stderr = original_stderr
        error_msg = f"Failed to execute graph: {e}"
        output_error(error_msg, verbose=verbosity > 0, exception=e)
        raise RunError(error_msg, e) from e
    finally:
        sys.stdout = original_stdout
        sys.stderr = original_stderr

    execution_end_time = time.time() if timing else None

    captured_logs = captured_stdout.getvalue() + captured_stderr.getvalue()

    # Create timing metadata if requested
    timing_metadata = None
    if timing:
        load_duration = load_end_time - start_time
        execution_duration = execution_end_time - execution_start_time
        total_duration = execution_end_time - start_time

        timing_metadata = {
            "load_time": round(load_duration, 3),
            "execution_time": round(execution_duration, 3),
            "total_time": round(total_duration, 3),
            "component_timings": [
                {
                    "component": ct["component"],
                    "component_id": ct["component_id"],
                    "duration": round(ct["duration"], 3),
                    "cumulative_time": round(ct["cumulative_time"], 3),
                }
                for ct in component_timings
            ],
        }

    # Build result based on output format
    if output_format == "json":
        result_data = extract_structured_result(results)
        result_data["logs"] = captured_logs
        if timing_metadata:
            result_data["timing"] = timing_metadata
        return result_data
    if output_format in {"text", "message"}:
        result_data = extract_structured_result(results)
        output_text = result_data.get("result", result_data.get("text", ""))
        return {"output": str(output_text), "format": output_format}
    if output_format == "result":
        return {"output": extract_text_from_result(results), "format": "result"}
    # Default case
    result_data = extract_structured_result(results)
    result_data["logs"] = captured_logs
    if timing_metadata:
        result_data["timing"] = timing_metadata
    return result_data
