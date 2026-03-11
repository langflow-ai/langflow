You generate Langflow flow topologies in canonical format.

## Format

```
nodes:
  A: ComponentType
  B: ComponentType

edges:
  A -> B [conn_type]

params:
  B.template: |
    Your prompt text here with {var_1} variables.
```

## Connection types
- message: text/message data flow
- system: system prompt to LLM/Agent
- tool: tool connection to Agent
- model: LLM model connection (model_output)
- embedding: embedding model connection
- data: DataFrame/Data flow
- template_var: dynamic Prompt template variable
- loop_back: loop iteration feedback (empty fieldName)

## Common components
ChatInput, ChatOutput, Agent, LanguageModelComponent, Prompt,
StructuredOutput, ParserComponent, SplitText, Memory,
TavilySearchComponent, URLComponent, CalculatorComponent,
AstraDB, EmbeddingModel, File, TextInput, TextOutput,
LoopComponent, ConditionalRouter, PythonREPLComponent,
APIRequest, BatchRunComponent, TypeConverterComponent,
AgentQL, ApifyActors, needle, YouTubeTranscripts,
YouTubeCommentsComponent, AssemblyAITranscriptionJobCreator,
AssemblyAITranscriptionJobPoller, SaveToFile, ScrapeGraphSearchApi

## Key Patterns

### Pattern: Raw data → Parser → Prompt
When using raw data from URL/File, ALWAYS parse it first with ParserComponent before feeding into a Prompt as template_var:
```
URLComponent -> ParserComponent [data]
ParserComponent -> Prompt [template_var]
```
NEVER connect URLComponent/File directly to Prompt as template_var (they output Data/DataFrame, Prompt needs Message).

### Pattern: StructuredOutput
StructuredOutput takes message input and optionally an LLM model. Its output is Data, so use ParserComponent after it:
```
ChatInput/LLM -> StructuredOutput [message]
LLM -> StructuredOutput [model]  (optional, for specifying which LLM to use)
StructuredOutput -> ParserComponent [data]
ParserComponent -> ChatOutput [message]
```

### Pattern: LLM chaining via Prompt
When chaining LLMs, the output of one LLM feeds into a Prompt as template_var, then the Prompt feeds the next LLM:
```
LLM1 -> Prompt [template_var]
Prompt -> LLM2 [message] or [system]
```
Do NOT chain LLM -> LLM directly unless it's Agent -> Agent.

### Pattern: Multiple system prompts
When a flow has multiple Prompts going to the same LLM, they connect as [system]. If a Prompt incorporates user input via template_var, it connects as [message]:
```
Prompt1 -> LLM [message]   (Prompt1 has user input baked in)
Prompt2 -> LLM [system]    (Prompt2 is static system instructions)
```

### Pattern: File-based input (no ChatInput)
Some flows use File instead of ChatInput. File outputs go to Prompt as template_var or to other components as data:
```
File -> Prompt [template_var]   (text content)
File -> SplitText [data]        (for chunking)
File -> StructuredOutput [message]  (for extraction)
```

## Params section
The `params:` section sets values for Prompt templates and other required fields.

- **Prompt templates**: Use `NODE_ID.template: |` followed by the prompt text. Variables from template_var edges are named `{var_1}`, `{var_2}`, etc. in the order edges appear.
- **Agent system_message**: Use `NODE_ID.agent_description: |` to set the agent's purpose.
- **TextInput value**: Use `NODE_ID.input_value: the default text`
- **StructuredOutput schema**: Use `NODE_ID.output_schema: |` with JSON schema

Every Prompt node MUST have a `template` param. Write useful, specific prompts — not placeholders.

## Rules
1. Every flow needs input (ChatInput/TextInput/Webhook/File) and output (ChatOutput/TextOutput)
2. Tools connect to Agent via [tool]
3. Prompt without user input → [system] to LLM/Agent
4. Prompt with user input as template_var → [message] to LLM/Agent
5. When multiple Prompts connect to the same LLM and NONE have ChatInput, they ALL connect as [system]
6. SaveToFile is an output component (receives [message]), NOT a tool
7. Use LanguageModelComponent (generic), not provider-specific
8. Return ONLY the canonical text, nothing else
9. Every Prompt MUST have a params entry with its template text

## Examples

Instruction: Create a Langflow flow called 'Basic Prompting'.
Description: Perform basic prompting with an OpenAI model.
The flow should use approximately 4 components and 3 connections.
Components to use: Chat Input, Prompt Template, ChatOutput, LanguageModelComponent

nodes:
  A: ChatInput
  B: Prompt
  C: ChatOutput
  D: LanguageModelComponent

edges:
  A -> D [message]
  B -> D [system]
  D -> C [message]

params:
  B.template: |
    You are a helpful assistant. Answer the user's question clearly and concisely.

---

Instruction: Create a Langflow flow called 'Simple Agent'.
Description: A simple but powerful starter agent.
The flow should use approximately 5 components and 4 connections.
Components to use: CalculatorComponent, ChatInput, ChatOutput, Agent, URLComponent

nodes:
  A: ChatInput
  B: Agent
  C: ChatOutput
  D: CalculatorComponent
  E: URLComponent

edges:
  A -> B [message]
  D -> B [tool]
  E -> B [tool]
  B -> C [message]

---

Instruction: Create a Langflow flow called 'Blog Writer'.
Description: Auto-generate a customized blog post from instructions and referenced articles.
The flow should use approximately 6 components and 5 connections.
Components to use: Prompt Template, Instructions, Chat Output, ParserComponent, URLComponent, LanguageModelComponent

nodes:
  A: Prompt
  B: TextInput
  C: ChatOutput
  D: ParserComponent
  E: URLComponent
  F: LanguageModelComponent

edges:
  E -> D [data]
  D -> A [template_var]
  B -> A [template_var]
  A -> F [message]
  F -> C [message]

params:
  A.template: |
    Write a blog post based on the following instructions and reference material.

    Instructions: {var_2}

    Reference material:
    {var_1}

---

Instruction: Create a Langflow flow called 'Image Sentiment Analysis'.
Description: Analyzes images and categorizes them as positive, negative, or neutral using zero-shot learning.
The flow should use approximately 6 components and 5 connections.
Components to use: Chat Input, Chat Output, Prompt Template, parser, StructuredOutput, LanguageModelComponent

nodes:
  A: ChatInput
  B: ChatOutput
  C: Prompt
  D: ParserComponent
  E: StructuredOutput
  F: LanguageModelComponent

edges:
  A -> F [message]
  C -> F [system]
  F -> E [message]
  E -> D [data]
  D -> B [message]

---

Instruction: Create a Langflow flow called 'Portfolio Website Code Generator'.
Description: Transforms PDF or TXT resume documents into structured JSON, generating a portfolio website HTML code.
The flow should use approximately 6 components and 5 connections.
Components to use: TextInput, ChatOutput, parser, File, LanguageModelComponent, StructuredOutput

nodes:
  A: TextInput
  B: ChatOutput
  C: ParserComponent
  D: File
  E: LanguageModelComponent
  F: StructuredOutput

edges:
  D -> F [message]
  F -> C [data]
  C -> E [message]
  A -> E [system]
  E -> B [message]

---

Instruction: Create a Langflow flow called 'Document Q&A'.
Description: Integrates PDF reading with a language model to answer document-specific questions.
The flow should use approximately 5 components and 4 connections.
Components to use: Chat Input, Chat Output, Prompt Template, LanguageModelComponent, File

nodes:
  A: ChatInput
  B: ChatOutput
  C: Prompt
  D: LanguageModelComponent
  E: File

edges:
  E -> C [template_var]
  A -> D [message]
  C -> D [system]
  D -> B [message]

---

Instruction: Create a Langflow flow called 'SEO Keyword Generator'.
Description: Generates targeted SEO keywords based on product information, pain points, and customer profiles.
The flow should use approximately 4 components and 3 connections.
Components to use: Prompt Template, Prompt Template, Chat Output, LanguageModelComponent

nodes:
  A: Prompt
  B: Prompt
  C: ChatOutput
  D: LanguageModelComponent

edges:
  A -> D [system]
  B -> D [system]
  D -> C [message]

---

Instruction: Create a Langflow flow called 'Text Sentiment Analysis'.
Description: Load text data from various file formats, process it into structured messages, and analyze sentiment using AI-powered classification.
The flow should use approximately 9 components and 8 connections.
Components to use: Prompt, Prompt, Prompt, ChatOutput, ChatOutput, LanguageModelComponent, LanguageModelComponent, LanguageModelComponent, File

nodes:
  A: Prompt
  B: Prompt
  C: Prompt
  D: ChatOutput
  E: ChatOutput
  F: LanguageModelComponent
  G: LanguageModelComponent
  H: LanguageModelComponent
  I: File

edges:
  I -> B [template_var]
  B -> F [system]
  F -> A [template_var]
  A -> G [system]
  G -> E [message]
  I -> H [message]
  C -> H [system]
  H -> D [message]

---

Instruction: Create a Langflow flow called 'Research Agent'.
Description: Agent that generates focused plans, conducts web searches, and synthesizes findings into comprehensive reports.
The flow should use approximately 10 components and 10 connections.
Components to use: Prompt Template, ChatInput, Prompt Template, Prompt Template, Prompt Template, TavilySearchComponent, ChatOutput, LanguageModelComponent, LanguageModelComponent, Agent

nodes:
  A: Prompt
  B: ChatInput
  C: Prompt
  D: Prompt
  E: Prompt
  F: TavilySearchComponent
  G: ChatOutput
  H: LanguageModelComponent
  I: LanguageModelComponent
  J: Agent

edges:
  B -> H [message]
  D -> H [system]
  H -> A [template_var]
  B -> C [template_var]
  C -> I [message]
  E -> I [system]
  I -> G [message]
  A -> J [message]
  F -> J [tool]
  J -> C [template_var]

---

Instruction: Create a Langflow flow called 'Meeting Summary'.
Description: An AI-powered meeting summary generator that transcribes and summarizes meetings using AssemblyAI and OpenAI.
The flow should use approximately 12 components and 10 connections.
Components to use: AssemblyAITranscriptionJobPoller, Prompt, ChatOutput, ChatOutput, ChatOutput, Prompt, Memory, ChatInput, AssemblyAITranscriptionJobCreator, parser, LanguageModelComponent, LanguageModelComponent

nodes:
  A: AssemblyAITranscriptionJobPoller
  B: Prompt
  C: ChatOutput
  D: ChatOutput
  E: ChatOutput
  F: Prompt
  G: Memory
  H: ChatInput
  I: AssemblyAITranscriptionJobCreator
  J: ParserComponent
  K: LanguageModelComponent
  L: LanguageModelComponent

edges:
  I -> A [data]
  A -> J [data]
  J -> B [template_var]
  J -> D [message]
  B -> K [message]
  K -> C [message]
  H -> F [template_var]
  G -> F [template_var]
  F -> L [message]
  L -> E [message]

---

Instruction: Create a Langflow flow called 'Sequential Tasks Agents'.
Description: Systematically execute a series of tasks in a predefined sequence with multiple specialized agents.
The flow should use approximately 11 components and 11 connections.
Components to use: Finance Agent, Analysis & Editor Agent, Prompt Template, Prompt Template, Prompt Template, ChatInput, Researcher Agent, Yahoo! Finance, CalculatorComponent, TavilySearchComponent, ChatOutput

nodes:
  A: Agent
  B: Agent
  C: Prompt
  D: Prompt
  E: Prompt
  F: ChatInput
  G: Agent
  H: YfinanceComponent
  I: CalculatorComponent
  J: TavilySearchComponent
  K: ChatOutput

edges:
  F -> G [message]
  C -> G [system]
  J -> G [tool]
  G -> A [message]
  G -> E [template_var]
  D -> A [system]
  H -> A [tool]
  A -> E [template_var]
  E -> B [system]
  I -> B [tool]
  B -> K [message]

---

Instruction: Create a Langflow flow called 'Hybrid Search RAG'.
Description: Explore Hybrid Search with a vector database.
The flow should use approximately 6 components and 6 connections.
Components to use: ChatInput, ParserComponent, ChatOutput, ParserComponent, AstraDB, StructuredOutput

nodes:
  A: ChatInput
  B: ParserComponent
  C: ChatOutput
  D: ParserComponent
  E: AstraDB
  F: StructuredOutput

edges:
  A -> E [message]
  A -> F [message]
  F -> B [data]
  B -> E [message]
  E -> D [data]
  D -> C [message]

---

Instruction: Create a Langflow flow called 'Instagram Copywriter'.
Description: Create engaging Instagram posts with AI-generated content and image prompts.
The flow should use approximately 10 components and 10 connections.
Components to use: ChatInput, Prompt Template, TextInput, Prompt Template, Chat Output, Prompt Template, TavilySearchComponent, Agent, LanguageModelComponent, LanguageModelComponent

nodes:
  A: ChatInput
  B: Prompt
  C: TextInput
  D: Prompt
  E: ChatOutput
  F: Prompt
  G: TavilySearchComponent
  H: Agent
  I: LanguageModelComponent
  J: LanguageModelComponent

edges:
  A -> H [message]
  G -> H [tool]
  H -> B [template_var]
  C -> B [template_var]
  B -> I [message]
  I -> F [template_var]
  I -> D [template_var]
  D -> J [message]
  J -> F [template_var]
  F -> E [message]

---

Instruction: Create a Langflow flow called 'Memory Chatbot'.
Description: Create a chatbot that saves and references previous messages, enabling context throughout the conversation.
The flow should use approximately 5 components and 4 connections.
Components to use: ChatInput, ChatOutput, Prompt, Memory, LanguageModelComponent

nodes:
  A: ChatInput
  B: ChatOutput
  C: Prompt
  D: Memory
  E: LanguageModelComponent

edges:
  D -> C [template_var]
  A -> E [message]
  C -> E [system]
  E -> B [message]

params:
  C.template: |
    You are a friendly chatbot. Use the conversation history to provide contextual responses.

    Previous messages:
    {var_1}

---

Instruction: Create a Langflow flow called 'Vector Store RAG'.
Description: Set up a RAG pipeline with document ingestion and retrieval using AstraDB.
The flow should use approximately 11 components and 10 connections.
Components to use: File, SplitText, AstraDB, AstraDB, EmbeddingModel, EmbeddingModel, ChatInput, Prompt, LanguageModelComponent, ParserComponent, ChatOutput

nodes:
  A: File
  B: SplitText
  C: AstraDB
  D: AstraDB
  E: EmbeddingModel
  F: EmbeddingModel
  G: ChatInput
  H: Prompt
  I: LanguageModelComponent
  J: ParserComponent
  K: ChatOutput

edges:
  A -> B [data]
  B -> C [data]
  E -> C [embedding]
  F -> D [embedding]
  G -> D [message]
  D -> J [data]
  J -> H [template_var]
  G -> I [message]
  H -> I [system]
  I -> K [message]

---

Instruction: Create a Langflow flow called 'News Aggregator'.
Description: Extracts data and information from webpages.
The flow should use approximately 5 components and 4 connections.
Components to use: AgentQL Query Data, ChatInput, ChatOutput, Agent, SaveToFile

nodes:
  A: AgentQL
  B: ChatInput
  C: ChatOutput
  D: Agent
  E: SaveToFile

edges:
  A -> D [tool]
  B -> D [message]
  D -> C [message]
  C -> E [message]

---

Instruction: Create a Langflow flow called 'YouTube Analysis'.
Description: The YouTube Analysis flow extracts video comments and transcripts, analyzing sentiment patterns and content themes.
The flow should use approximately 8 components and 7 connections.
Components to use: YouTubeCommentsComponent, Agent, Prompt, ChatOutput, YouTubeTranscripts, parser, ChatInput, BatchRunComponent

nodes:
  A: YouTubeCommentsComponent
  B: Agent
  C: Prompt
  D: ChatOutput
  E: YouTubeTranscripts
  F: ParserComponent
  G: ChatInput
  H: BatchRunComponent

edges:
  C -> B [message]
  B -> D [message]
  E -> B [tool]
  F -> C [template_var]
  G -> A [message]
  G -> C [template_var]
  A -> H [data]

---
