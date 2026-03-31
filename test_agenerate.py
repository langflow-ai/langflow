"""Test script for generate_prototypical_instances function."""

import asyncio
import os
from pydantic import BaseModel, Field


async def test_generate():
    """Test the generate_prototypical_instances function."""
    try:
        from agentics.core.atype import create_pydantic_model
        from agentics.core.transducible_functions import generate_prototypical_instances
        from crewai import LLM
    except ImportError as e:
        print(f"Import error: {e}")
        print("Make sure agentics-py and crewai are installed:")
        print("  uv pip install agentics-py crewai")
        return

    # Check for OpenAI API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY environment variable not set")
        print("Set it with: export OPENAI_API_KEY='your-key-here'")
        return

    print("Creating LLM instance...")
    llm = LLM(model="gpt-3.5-turbo", api_key=api_key)
    print(f"LLM created: {llm}")

    # Create a simple schema
    print("\nCreating schema...")
    schema_fields = {
        "name": (str, Field(description="Person's full name")),
        "age": (int, Field(description="Person's age in years")),
        "email": (str, Field(description="Person's email address")),
    }
    atype = create_pydantic_model(schema_fields, name="Person")
    print(f"Schema created: {atype}")

    # Test with instructions
    instructions = "Generate realistic person data with diverse names and ages between 20-60"
    print(f"\nInstructions: {instructions}")

    print("\nCalling generate_prototypical_instances...")
    try:
        result = await generate_prototypical_instances(
            atype,
            n_instances=3,
            llm=llm,
            instructions=instructions,
        )
        print(f"\nResult type: {type(result)}")
        print(f"Result: {result}")
        
        if result:
            print(f"\nGenerated {len(result)} instances:")
            for i, instance in enumerate(result, 1):
                print(f"  {i}. {instance}")
        else:
            print("\nNo instances generated (result is None or empty)")
            
    except Exception as e:
        print(f"\nError during generation: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("Testing generate_prototypical_instances...")
    print("=" * 60)
    asyncio.run(test_generate())

# Made with Bob
