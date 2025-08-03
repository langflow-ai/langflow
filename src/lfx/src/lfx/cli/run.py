import json
import sys
import tempfile
from functools import partial
from io import StringIO
from pathlib import Path

import typer
from asyncer import syncify
from loguru import logger

from lfx.cli.script_loader import (
    extract_structured_result,
    extract_text_from_result,
    find_graph_variable,
    load_graph_from_script,
)
from lfx.cli.validation import validate_global_variables_for_env
from lfx.schema.schema import InputValueRequest


def output_error(error_message: str, *, verbose: bool) -> None:
    """Output error in JSON format to stdout when not verbose, or to stderr when verbose."""
    if verbose:
        typer.echo(f"✗ {error_message}", file=sys.stderr)
    else:
        error_response = {
            "success": False,
            "error": error_message,
            "type": "error",
        }
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
    stdin: bool | None = typer.Option(
        default=False,
        show_default=True,
        help="Read JSON flow content from stdin (alternative to script_path)",
    ),
    *,
    check_variables: bool = typer.Option(
        default=True,
        show_default=True,
        help="Check global variables for environment compatibility",
    ),
    verbose: bool = typer.Option(
        default=False,
        show_default=True,
        help="Show diagnostic output and execution details",
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
        output_format: Format for output (json, text, message, or result)
        flow_json: Inline JSON flow content as a string
        stdin: Read JSON flow content from stdin
        check_variables: Check global variables for environment compatibility
    """

    def verbose_print(message: str) -> None:
        if verbose:
            typer.echo(message, file=sys.stderr)

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
        verbose_print("Processing inline JSON content...")
        try:
            json_data = json.loads(flow_json)
            verbose_print("✓ JSON content is valid")
            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as temp_file:
                json.dump(json_data, temp_file, indent=2)
                temp_file_to_cleanup = temp_file.name
            script_path = Path(temp_file_to_cleanup)
            verbose_print(f"✓ Created temporary file: {script_path}")
        except json.JSONDecodeError as e:
            output_error(f"Invalid JSON content: {e}", verbose=verbose)
            raise typer.Exit(1) from e
        except Exception as e:
            output_error(f"Error processing JSON content: {e}", verbose=verbose)
            raise typer.Exit(1) from e
    elif stdin:
        verbose_print("Reading JSON content from stdin...")
        try:
            stdin_content = sys.stdin.read().strip()
            if not stdin_content:
                output_error("No content received from stdin", verbose=verbose)
                raise typer.Exit(1)
            json_data = json.loads(stdin_content)
            verbose_print("✓ JSON content from stdin is valid")
            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as temp_file:
                json.dump(json_data, temp_file, indent=2)
                temp_file_to_cleanup = temp_file.name
            script_path = Path(temp_file_to_cleanup)
            verbose_print(f"✓ Created temporary file from stdin: {script_path}")
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
        verbose_print(f"Analyzing {file_type}: {script_path}")
        if file_extension == ".py":
            graph_info = find_graph_variable(script_path)
            if not graph_info:
                error_msg = (
                    "No 'graph' variable found in the script. Expected to find an assignment like: graph = Graph(...)"
                )
                raise ValueError(error_msg)
            verbose_print(f"✓ Found 'graph' variable at line {graph_info['line_number']}")
            verbose_print(f"  Type: {graph_info['type']}")
            verbose_print(f"  Source: {graph_info['source_line']}")
            verbose_print("\nLoading and executing script...")
            graph = load_graph_from_script(script_path)
        elif file_extension == ".json":
            verbose_print("✓ Valid JSON flow file detected")
            verbose_print("\nLoading and executing JSON flow...")
            from lfx.load import aload_flow_from_json

            graph = await aload_flow_from_json(script_path, disable_logs=not verbose)
    except Exception as e:
        if verbose:
            logger.exception("Failed to load graph")
        output_error(f"Failed to load graph: {e}", verbose=verbose)
        if temp_file_to_cleanup:
            try:
                Path(temp_file_to_cleanup).unlink()
                verbose_print(f"✓ Cleaned up temporary file: {temp_file_to_cleanup}")
            except OSError:
                pass
        raise typer.Exit(1) from e

    inputs = InputValueRequest(input_value=final_input_value) if final_input_value else None
    verbose_print("Preparing graph for execution...")
    try:
        graph.prepare()

        # Validate global variables for environment compatibility

        if check_variables:
            validation_errors = validate_global_variables_for_env(graph)
            if validation_errors:
                error_details = "Global variable validation failed: " + "; ".join(validation_errors)
                output_error(error_details, verbose=verbose)
            if temp_file_to_cleanup:
                try:
                    Path(temp_file_to_cleanup).unlink()
                    verbose_print(f"✓ Cleaned up temporary file: {temp_file_to_cleanup}")
                except OSError:
                    pass
            if validation_errors:
                raise typer.Exit(1)
        else:
            verbose_print("✓ Global variable validation skipped")
    except Exception as e:
        output_error(f"Failed to prepare graph: {e}", verbose=verbose)
        if temp_file_to_cleanup:
            try:
                Path(temp_file_to_cleanup).unlink()
                verbose_print(f"✓ Cleaned up temporary file: {temp_file_to_cleanup}")
            except OSError:
                pass
        raise typer.Exit(1) from e

    captured_stdout = StringIO()
    captured_stderr = StringIO()
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    try:
        sys.stdout = captured_stdout
        sys.stderr = captured_stderr
        results = [result async for result in graph.async_start(inputs)]
    except Exception as e:
        sys.stdout = original_stdout
        sys.stderr = original_stderr
        output_error(f"Failed to execute graph: {e}", verbose=verbose)
        if temp_file_to_cleanup:
            try:
                Path(temp_file_to_cleanup).unlink()
                verbose_print(f"✓ Cleaned up temporary file: {temp_file_to_cleanup}")
            except OSError:
                pass
        raise typer.Exit(1) from e
    finally:
        sys.stdout = original_stdout
        sys.stderr = original_stderr
        if temp_file_to_cleanup:
            try:
                Path(temp_file_to_cleanup).unlink()
                verbose_print(f"✓ Cleaned up temporary file: {temp_file_to_cleanup}")
            except OSError:
                pass

    captured_logs = captured_stdout.getvalue() + captured_stderr.getvalue()
    if output_format == "json":
        result_data = extract_structured_result(results)
        result_data["logs"] = captured_logs
        indent = 2 if verbose else None
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
        indent = 2 if verbose else None
        typer.echo(json.dumps(result_data, indent=indent))
