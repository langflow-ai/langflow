import asyncio
from pathlib import Path

from lfx.run.base import run_flow

if __name__ == "__main__":
    # Path to LFX_TEST3.json
    flow_path = Path(__file__).parent.parent / "flows" / "LFX_TEST3.json"

    async def main():
        # Call run_flow with the flow path (minimal test, add parameters as needed)
        result = await run_flow(
            script_path=flow_path,
            input_value=None,  # or provide string if required
            global_variables={
                "FLOW_ID": "LFX_TEST3",
                "OPENAI_API_KEY": "sk-proj-1234567890",
            },
            verbose=True,
            check_variables=False,
        )
        print(result)

    asyncio.run(main())
