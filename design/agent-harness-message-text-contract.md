# Message, text, and the Agent Harness instructions contract

Research date: 2026-09-15. Research baseline: `22a1791eddc83a686ab2508f752467a168faf8f7`. Official documentation consulted: Langflow 1.12.x.

## Implemented correction

Instructions now accepts the existing Prompt Template's Message output directly. Discovery and Run Flow expose the selected terminal output without requiring a dedicated output component. The runtime validates that the actual Message or string contains nonempty text and preserves Message values on flow edges. New Instructions flows contain a Prompt Template, with literal braces and Agent placeholders preserved when copying the form value.

The duplicate System Prompt Builder component and catalog entry have been removed. The reusable slot is named Instructions and advertises Message as its output type. The user explicitly confirmed that compatibility with the newly introduced System Prompt Builder flows was unnecessary. Existing Langflow string outputs remain supported.

Integration coverage exercises real Prompt execution through the Agent, source revision checks, nested prompt variables, immutable dependency snapshots, and archive round trips. The findings below describe the research baseline that led to this correction.

## Finding

The user's correction is supported: **`Message` is Langflow's normal component value for carrying text, including prompts and simple non-chat text.** Treating a Prompt Template's `Message` as an incompatible kind of content was the wrong architectural justification for introducing a required System Prompt Builder. The local Prompt Template constructs a `Message`, legacy Text Input constructs a `Message`, and text inputs already know how to extract the text. [Prompt Template implementation](/Users/ogabrielluiz/Projects/langflow-wt-lfx-proj/src/lfx/src/lfx/components/models_and_agents/prompt.py:94), [Text Input implementation](/Users/ogabrielluiz/Projects/langflow-wt-lfx-proj/src/lfx/src/lfx/components/input_output/text.py:48), [MessageTextInput conversion](/Users/ogabrielluiz/Projects/langflow-wt-lfx-proj/src/lfx/src/lfx/inputs/inputs.py:431).

This is a content convention with explicit conversion at component boundaries. It does **not** mean that Python `str`, the port type name `Text`, and the structured `Message` class are universally interchangeable. The current canvas preserves their declared names and has no global Message/Text alias. [Port compatibility](/Users/ogabrielluiz/Projects/langflow-wt-lfx-proj/src/frontend/src/utils/reactflowUtils.ts:1207), [port tooltip rendering](/Users/ogabrielluiz/Projects/langflow-wt-lfx-proj/src/frontend/src/CustomNodes/GenericNode/components/HandleTooltipComponent/index.tsx:47).

## What official documentation says

- `Message` is the structured carrier for text and optional metadata. Legacy Text Input/Output use it for simple strings without conversational metadata; Chat Input/Output use it for conversations. Components determine which fields and conversions are required. [Langflow data types](https://docs.langflow.org/data-types#message).
- Prompt Template supplies instructions and context to an LLM or agent, with fixed content and dynamic variables. This is already its intended role. [Prompt Template](https://docs.langflow.org/components-prompts).
- Chat Input builds a Message from text/files. Chat Output accepts Message, JSON, or Table and converts as necessary before emitting a Message. [Chat Input and Output](https://docs.langflow.org/chat-input-and-output).

The public documentation and local code agree on this text-carrying role. Neither establishes blanket equivalence between every string port and every Message port.

## Existing component conventions

| Component/input | Declared connection type | Value used or returned |
| --- | --- | --- |
| Prompt Template | Output `Message` | Formatted prompt wrapped in a Message |
| Legacy Text Input | Output `Message` | Message containing the text |
| `MessageInput` | Accepts `Message` | Preserves a Message; wraps raw strings in a Message |
| `MessageTextInput` | Accepts `Message`; native field is text | Extracts `Message.text`; leaves a raw string as text |
| `MultilineInput` | Inherits `MessageTextInput` | Same extraction, with multiline editing |
| Agent Instructions | `MultilineInput` | Text extracted from a connected prompt |

Sources: [Prompt Template](/Users/ogabrielluiz/Projects/langflow-wt-lfx-proj/src/lfx/src/lfx/components/models_and_agents/prompt.py:94), [Text Input](/Users/ogabrielluiz/Projects/langflow-wt-lfx-proj/src/lfx/src/lfx/components/input_output/text.py:48), [MessageInput](/Users/ogabrielluiz/Projects/langflow-wt-lfx-proj/src/lfx/src/lfx/inputs/inputs.py:375), [MessageTextInput](/Users/ogabrielluiz/Projects/langflow-wt-lfx-proj/src/lfx/src/lfx/inputs/inputs.py:397), [MultilineInput](/Users/ogabrielluiz/Projects/langflow-wt-lfx-proj/src/lfx/src/lfx/inputs/inputs.py:477), [Agent Instructions field](/Users/ogabrielluiz/Projects/langflow-wt-lfx-proj/src/lfx/src/lfx/components/models_and_agents/agent.py:199).

The Agent also explicitly normalizes Message-like values before substituting instruction placeholders. Therefore the earlier assertion that the Agent needs an entirely new Message-to-text conversion was too broad: that conversion already exists. [Agent normalization](/Users/ogabrielluiz/Projects/langflow-wt-lfx-proj/src/lfx/src/lfx/components/models_and_agents/agent.py:558), [text extraction](/Users/ogabrielluiz/Projects/langflow-wt-lfx-proj/src/lfx/src/lfx/components/models_and_agents/agent.py:116).

## What the canvas actually equates

The canvas gives `str`, `Text`, and `Message` the same indigo color, but the tooltip displays the declared type rather than relabeling Message as Text. Inputs display `input_types`; outputs display the selected declared output type. [Colors](/Users/ogabrielluiz/Projects/langflow-wt-lfx-proj/src/frontend/src/utils/styleUtils.ts:152), [input tooltip source](/Users/ogabrielluiz/Projects/langflow-wt-lfx-proj/src/frontend/src/CustomNodes/GenericNode/components/RenderInputParameters/index.tsx:132), [output tooltip source](/Users/ogabrielluiz/Projects/langflow-wt-lfx-proj/src/frontend/src/CustomNodes/GenericNode/components/NodeOutputParameter/index.tsx:78).

Global type compatibility currently aliases only `Data`/`JSON` and `DataFrame`/`Table`. A connection can match either an explicit accepted input type or the input's native field type. Thus Message reaches a `MessageTextInput` through its explicit `Message` acceptance, while a raw `str` can match its native string field. This does not imply that a port accepting only `Text` automatically accepts Message, or vice versa. [Compatibility aliases](/Users/ogabrielluiz/Projects/langflow-wt-lfx-proj/src/frontend/src/utils/reactflowUtils.ts:1207), [connection checks](/Users/ogabrielluiz/Projects/langflow-wt-lfx-proj/src/frontend/src/utils/reactflowUtils.ts:488).

Backend metadata generation also distinguishes these names: `format_type(str)` becomes the port name `Text`, while the Message type keeps its class name. Separately, Python string parameters are mapped to `MessageTextInput`, which is how canonical Message connections can supply their content to string-using components. [Output type formatting](/Users/ogabrielluiz/Projects/langflow-wt-lfx-proj/src/lfx/src/lfx/helpers/custom.py:6), [input schema mapping](/Users/ogabrielluiz/Projects/langflow-wt-lfx-proj/src/lfx/src/lfx/io/schema.py:77).

## Where the research baseline diverged

The harness's Instructions output discovery introduces two independent restrictions:

1. It accepts only declared `str`/`Text` outputs, excluding canonical `Message` outputs. [Instructions type filter](/Users/ogabrielluiz/Projects/langflow-wt-lfx-proj/src/lfx/src/lfx/projects/bindings.py:117).
2. It requires a node marked `is_output` with no successors. An ordinary leaf Prompt Template does not carry that output designation. [Terminal filter](/Users/ogabrielluiz/Projects/langflow-wt-lfx-proj/src/lfx/src/lfx/projects/bindings.py:143).

System Prompt Builder satisfied those restrictions by marking itself as an output, taking the text through a `MultilineInput`, and returning a nonempty string. It added no templating capability. Its component file has now been removed.

A local execution probe run during this investigation returned `Message(text='Research with citations.')` from Prompt Template. Generated Prompt Template metadata exposed `['Message']` and no explicit output designation; the current Instructions discovery returned no choices. The System Prompt Builder metadata exposed `['Text']`, an explicit output designation, and an eligible Instructions choice. A separate input probe confirmed that MessageInput retains the Message object while MessageTextInput and MultilineInput extract its string text. These probes support the source-level distinction above; they are not an end-to-end execution test of a changed harness.

An additional in-memory probe varied only the declared type and output designation of a Prompt node:

| Declared output | `is_output` | Instructions choices | Run Flow exposed outputs |
| --- | --- | --- | --- |
| Message | false | 0 | 0 |
| Message | true | 0 | 1 |
| Text | false | 0 | 0 |
| Text | true | 1 | 1 |

This isolates the two restrictions. Run Flow's output exposure independently requires `is_output` and no successors, so binding discovery is not the only place that needs correction. [Run Flow output exposure](/Users/ogabrielluiz/Projects/langflow-wt-lfx-proj/src/lfx/src/lfx/base/tools/run_flow.py:705). All probes used `LANGFLOW_UPDATE_STARTER_PROJECTS=false uv run --no-sync`; no provider calls or application source changes were required.

## Correction rationale

Allow the user to select a compatible Prompt Template leaf directly as the Instructions result. Accept canonical `Message` alongside existing string output compatibility, extract and validate its text at the harness boundary, and preserve reviewed revisions and the other binding safeguards. Update both discovery and flow-result resolution to support the selected ordinary leaf; adding Message to the allowed type set alone does not remove the output-designation restriction.

The implementation follows the existing Langflow conventions and removes the unnecessary adapter. The regression tests use the real Prompt Template and demonstrate both output discovery and successful bound execution; checking only the former System Prompt Builder would not establish this interoperability.
