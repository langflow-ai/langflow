import json
import re
import sys
import tempfile
from functools import partial
from io import StringIO
from pathlib import Path

import typer
from asyncer import syncify

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


def output_error(error_message: str, *, verbose: bool, exception: Exception | None = None) -> None:
    """Output error in JSON format to stdout when not verbose, or to stderr when verbose."""
    if verbose:
        typer.echo(f"{error_message}", file=sys.stderr)

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

    typer.echo(json.dumps(error_response))


@partial(syncify, raise_sync_error=False)
async def run(
    script_path: Path | None = typer.Argument(  # noqa: B008
        None, help="Path to the Python script (.py) or JSON flow (.json) containing a graph"
    ),
    input_value: str | None = typer.Argument(None, help="Input value to pass to the graph"),
    input_value_option: str | None = typer.Option(
        None,
        "--input-value",
        help="Input value to pass to the graph (alternative to positional argument)",
    ),
    output_format: str = typer.Option(
        "json",
        "--format",
        "-f",
        help="Output format: json, text, message, or result",
    ),
    flow_json: str | None = typer.Option(
        None,
        "--flow-json",
        help=("Inline JSON flow content as a string (alternative to script_path)"),
    ),
    *,
    stdin: bool | None = typer.Option(
        default=False,
        flag_value="--stdin",
        show_default=True,
        help="Read JSON flow content from stdin (alternative to script_path)",
    ),
    check_variables: bool = typer.Option(
        default=True,
        show_default=True,
        help="Check global variables for environment compatibility",
    ),
    verbose: bool = typer.Option(
        False,  # noqa: FBT003
        "-v",
        "--verbose",
        help="Show basic progress information",
    ),
    verbose_detailed: bool = typer.Option(
        False,  # noqa: FBT003
        "-vv",
        help="Show detailed progress and debug information",
    ),
    verbose_full: bool = typer.Option(
        False,  # noqa: FBT003
        "-vvv",
        help="Show full debugging output including component logs",
    ),
    timing: bool = typer.Option(
        default=False,
        show_default=True,
        help="Include detailed timing information in output",
    ),
) -> None:
    """Execute a Langflow graph script or JSON flow and return the result.

    This command analyzes and executes either a Python script containing a Langflow graph,
    a JSON flow file, inline JSON, or JSON from stdin, returning the result in the specified format.
    By default, output is minimal for use in containers and serverless environments.

    Args:
        script_path: Path to the Python script (.py) or JSON flow (.json) containing a graph
        input_value: Input value to pass to the graph (positional argument)
        input_value_option: Input value to pass to the graph (alternative option)
        verbose: Show diagnostic output and execution details
        verbose_detailed: Show detailed progress and debug information (-vv)
        verbose_full: Show full debugging output including component logs (-vvv)
        output_format: Format for output (json, text, message, or result)
        flow_json: Inline JSON flow content as a string
        stdin: Read JSON flow content from stdin
        check_variables: Check global variables for environment compatibility
        timing: Include detailed timing information in output
    """
    # Start timing if requested
    import time

    # Configure logger based on verbosity level
    from lfx.log.logger import configure

    if verbose_full:
        configure(log_level="DEBUG", output_file=sys.stderr)  # Show everything including component debug logs
        verbosity = 3
    elif verbose_detailed:
        configure(log_level="DEBUG", output_file=sys.stderr)  # Show debug and above
        verbosity = 2
    elif verbose:
        configure(log_level="INFO", output_file=sys.stderr)  # Show info and above including our CLI info messages
        verbosity = 1
    else:
        configure(log_level="CRITICAL", output_file=sys.stderr)  # Only critical errors
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
        raise typer.Exit(1)

    temp_file_to_cleanup = None

    if flow_json is not None:
        if verbosity > 0:
            typer.echo("Processing inline JSON content...", file=sys.stderr)
        try:
            json_data = json.loads(flow_json)
            if verbosity > 0:
                typer.echo("JSON content is valid", file=sys.stderr)
            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as temp_file:
                json.dump(json_data, temp_file, indent=2)
                temp_file_to_cleanup = temp_file.name
            script_path = Path(temp_file_to_cleanup)
            if verbosity > 0:
                typer.echo(f"Created temporary file: {script_path}", file=sys.stderr)
        except json.JSONDecodeError as e:
            output_error(f"Invalid JSON content: {e}", verbose=verbose)
            raise typer.Exit(1) from e
        except Exception as e:
            output_error(f"Error processing JSON content: {e}", verbose=verbose)
            raise typer.Exit(1) from e
    elif stdin:
        if verbosity > 0:
            typer.echo("Reading JSON content from stdin...", file=sys.stderr)
        try:
            stdin_content = sys.stdin.read().strip()
            if not stdin_content:
                output_error("No content received from stdin", verbose=verbose)
                raise typer.Exit(1)
            json_data = json.loads(stdin_content)
            if verbosity > 0:
                typer.echo("JSON content from stdin is valid", file=sys.stderr)
            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as temp_file:
                json.dump(json_data, temp_file, indent=2)
                temp_file_to_cleanup = temp_file.name
            script_path = Path(temp_file_to_cleanup)
            if verbosity > 0:
                typer.echo(f"Created temporary file from stdin: {script_path}", file=sys.stderr)
        except json.JSONDecodeError as e:
            output_error(f"Invalid JSON content from stdin: {e}", verbose=verbose)
            raise typer.Exit(1) from e
        except Exception as e:
            output_error(f"Error reading from stdin: {e}", verbose=verbose)
            raise typer.Exit(1) from e

    try:
        if not script_path or not script_path.exists():
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
            typer.echo(f"Analyzing {file_type}: {script_path}", file=sys.stderr)
        if file_extension == ".py":
            graph_info = find_graph_variable(script_path)
            if not graph_info:
                error_msg = (
                    "No 'graph' variable found in the script. Expected to find an assignment like: graph = Graph(...)"
                )
                raise ValueError(error_msg)
            if verbosity > 0:
                typer.echo(f"Found 'graph' variable at line {graph_info['line_number']}", file=sys.stderr)
                typer.echo(f"Type: {graph_info['type']}", file=sys.stderr)
                typer.echo(f"Source: {graph_info['source_line']}", file=sys.stderr)
                typer.echo("Loading and executing script...", file=sys.stderr)
            graph = load_graph_from_script(script_path)
        elif file_extension == ".json":
            if verbosity > 0:
                typer.echo("Valid JSON flow file detected", file=sys.stderr)
                typer.echo("Loading and executing JSON flow", file=sys.stderr)
            from lfx.load import aload_flow_from_json

            graph = await aload_flow_from_json(script_path, disable_logs=not verbose)
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

        output_error(f"Failed to load graph. {e}", verbose=verbose, exception=e)
        if temp_file_to_cleanup:
            try:
                Path(temp_file_to_cleanup).unlink()
                logger.info(f"Cleaned up temporary file: {temp_file_to_cleanup}")
            except OSError:
                pass
        raise typer.Exit(1) from e

    inputs = InputValueRequest(input_value=final_input_value) if final_input_value else None

    # Mark end of loading phase if timing
    load_end_time = time.time() if timing else None

    if verbosity > 0:
        typer.echo("Preparing graph for execution...", file=sys.stderr)
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
            if temp_file_to_cleanup:
                try:
                    Path(temp_file_to_cleanup).unlink()
                    logger.info(f"Cleaned up temporary file: {temp_file_to_cleanup}")
                except OSError:
                    pass
            if validation_errors:
                raise typer.Exit(1)
            logger.info("Global variable validation passed")
        else:
            logger.info("Global variable validation skipped")
    except Exception as e:
        error_type = type(e).__name__
        logger.info(f"Graph preparation failed with {error_type}")

        if verbosity > 0:
            logger.debug(f"Preparation error: {e!s}")
            logger.exception("Failed to prepare graph - full traceback:")

        output_error(f"Failed to prepare graph: {e}", verbose=verbose, exception=e)
        if temp_file_to_cleanup:
            try:
                Path(temp_file_to_cleanup).unlink()
                logger.info(f"Cleaned up temporary file: {temp_file_to_cleanup}")
            except OSError:
                pass
        raise typer.Exit(1) from e

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

    try:
        sys.stdout = captured_stdout
        # Don't capture stderr at high verbosity levels to avoid duplication with direct logging
        if verbosity < VERBOSITY_FULL:
            sys.stderr = captured_stderr
        results = []

        logger.info("Starting graph execution...", level="DEBUG")
        result_count = 0

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

        if temp_file_to_cleanup:
            try:
                Path(temp_file_to_cleanup).unlink()
                logger.info(f"Cleaned up temporary file: {temp_file_to_cleanup}")
            except OSError:
                pass
        sys.stdout = original_stdout
        sys.stderr = original_stderr
        output_error(f"Failed to execute graph: {e}", verbose=verbosity > 0, exception=e)
        raise typer.Exit(1) from e
    finally:
        sys.stdout = original_stdout
        sys.stderr = original_stderr
        if temp_file_to_cleanup:
            try:
                Path(temp_file_to_cleanup).unlink()
                logger.info(f"Cleaned up temporary file: {temp_file_to_cleanup}")
            except OSError:
                pass

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

    if output_format == "json":
        result_data = extract_structured_result(results)
        result_data["logs"] = captured_logs
        if timing_metadata:
            result_data["timing"] = timing_metadata
        indent = 2 if verbosity > 0 else None
        typer.echo(json.dumps(result_data, indent=indent))
    elif output_format in {"text", "message"}:
        result_data = extract_structured_result(results)
        output_text = result_data.get("result", result_data.get("text", ""))
        typer.echo(str(output_text))
    elif output_format == "result":
        typer.echo(extract_text_from_result(results))
    else:
        result_data = extract_structured_result(results)
        result_data["logs"] = captured_logs
        if timing_metadata:
            result_data["timing"] = timing_metadata
        indent = 2 if verbosity > 0 else None
        typer.echo(json.dumps(result_data, indent=indent))
