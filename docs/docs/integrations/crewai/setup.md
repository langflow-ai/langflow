import Admonition from "@theme/Admonition";

# Using CrewAI Components in Langflow

Langflow provides the following CrewAI components:

- **[CrewAIAgent](./agent)**: Represents an agent of CrewAI.
- **[CrewAITask](./task)**: Each task must have a description, an expected output, and an agent responsible for execution.
- **[CrewAICrew](./crew)**: Represents a group of agents, defining how they should collaborate and the tasks they should perform.

Refer to the individual component documentation for more details on how to use each component in your Langflow flows.

## Components Compatibility

- **CrewAIAgent**:
  - Compatible with CrewAITask and CrewAICrew components.
- **CrewAITask**:
  - Compatible with CrewAIAgent and CrewAICrew components.
- **CrewAICrew**:
  - Compatible with CrewAIAgent and CrewAITask components.

## Additional Resources

- [CrewAI API Documentation](https://docs.crewai.com/how-to/Creating-a-Crew-and-kick-it-off/)
- [CrewAI Examples](https://github.com/joaomdmoura/crewAI-examples/tree/main)

If you encounter any issues or have questions, please reach out to our support team or consult the Langflow community forums.
