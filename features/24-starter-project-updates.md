# Feature 24: Starter Project Updates

## Summary

This feature updates 27 starter project JSON files in `src/backend/base/langflow/initial_setup/starter_projects/`. The changes follow several patterns:

### Pattern 1: Model Field Cleanup

The `model` field in Agent/LLM components is cleaned up:
- **Remove `"options": []`** -- the empty options array is removed from model fields
- **Change `"value": []` to `"value": ""`** -- model value changed from empty array to empty string
- **Remove `"input_types": ["LanguageModel"]`** and replace with `"input_types": []`** -- clearing input type constraints

This cleanup ensures that model fields start in a clean, unselected state rather than carrying stale option lists or array values.

### Pattern 2: TextInput Legacy Marking

TextInput components are marked as legacy:
- **`"legacy": false` changed to `"legacy": true`** -- at the node level
- **`code_hash` updated** from `"518f16485886"` to `"dea80583c672"`
- **Embedded code `"value"` updated** -- the inline Python source adds `legacy = True` and `replacement = ["input_output.JSONInput"]` to the class definition

This marks TextInput as a deprecated component that should be replaced by JSONInput.

### Pattern 3: Component Code Updates (Embedded)

Some files carry updated embedded component code (File component, Knowledge Base component, YouTube Comments component, MCPTools component, Save File component). These show as `code_hash` changes with updated `"value"` strings containing the full Python source. The actual code changes are documented in their respective feature files.

### Pattern 4: Misc Field Additions

A few files add new fields to components:
- **`"override_skip": false`** -- added to context_id fields
- **`"track_in_telemetry": false`** -- added to context_id fields

---

## Diff Statistics

```
 Basic Prompting.json               |   4 +-
 Blog Writer.json                   |   6 +-
 Custom Component Generator.json    |   4 +-
 Document Q&A.json                  |   4 +-
 Instagram Copywriter.json          |   9 +-
 Invoice Summarizer.json            |   3 +-
 Knowledge Ingestion.json           |   4 +-
 Knowledge Retrieval.json           |  62 +++++++-
 Market Research.json               |   3 +-
 Meeting Summary.json               |   2 +
 Memory Chatbot.json                |   2 +
 News Aggregator.json               |   7 +-
 Nvidia Remix.json                  |   9 +-
 Pokédex Agent.json                 |   3 +-
 Portfolio Website Code Generator   |  10 +-
 Price Deal Finder.json             |   3 +-
 Research Agent.json                |   3 +-
 SaaS Pricing.json                  |   3 +-
 Search agent.json                  |   3 +-
 Sequential Tasks Agents.json       |   9 +-
 Simple Agent.json                  |   3 +-
 Social Media Agent.json            |   3 +-
 Text Sentiment Analysis.json       |   4 +-
 Travel Planning Agents.json        |   9 +-
 Twitter Thread Generator.json      |  36 ++---
 Vector Store RAG.json              |   4 +-
 Youtube Analysis.json              | 168 +--------------------
 27 files changed, 125 insertions(+), 255 deletions(-)
```

---

## Per-File Diffs

All files are in `src/backend/base/langflow/initial_setup/starter_projects/`.

---

### Basic Prompting.json

**Changes:** Model `input_types` cleanup (remove `LanguageModel` constraint).

```diff
diff --git a/src/backend/base/langflow/initial_setup/starter_projects/Basic Prompting.json b/src/backend/base/langflow/initial_setup/starter_projects/Basic Prompting.json
index 0b1836f47f..4678b025c8 100644
--- a/src/backend/base/langflow/initial_setup/starter_projects/Basic Prompting.json
+++ b/src/backend/base/langflow/initial_setup/starter_projects/Basic Prompting.json
@@ -1073,9 +1073,7 @@
                   }
                 },
                 "info": "Select your model provider",
-                "input_types": [
-                  "LanguageModel"
-                ],
+                "input_types": [],
                 "list": false,
                 "list_add_label": "Add More",
                 "model_type": "language",
```

---

### Blog Writer.json

**Changes:** TextInput marked as legacy with `legacy = True` and `replacement = ["input_output.JSONInput"]`.

```diff
diff --git a/src/backend/base/langflow/initial_setup/starter_projects/Blog Writer.json b/src/backend/base/langflow/initial_setup/starter_projects/Blog Writer.json
index 9ebbdefccc..92419d89e8 100644
--- a/src/backend/base/langflow/initial_setup/starter_projects/Blog Writer.json
+++ b/src/backend/base/langflow/initial_setup/starter_projects/Blog Writer.json
@@ -377,10 +377,10 @@
             ],
             "frozen": false,
             "icon": "type",
-            "legacy": false,
+            "legacy": true,
             "lf_version": "1.4.2",
             "metadata": {
-              "code_hash": "518f16485886",
+              "code_hash": "dea80583c672",
               "dependencies": {
                 "dependencies": [
                   {
@@ -428,7 +428,7 @@
                 "show": true,
                 "title_case": false,
                 "type": "code",
-                "value": "...TextInputComponent...name = \"TextInput\"\n\n..."
+                "value": "...TextInputComponent...name = \"TextInput\"\n    legacy = True\n    replacement = [\"input_output.JSONInput\"]\n\n..."
```

> **Note:** The `"value"` field contains the full TextInput Python source as a single-line JSON string. The only change within that code is adding `legacy = True` and `replacement = ["input_output.JSONInput"]` to the class body. The full single-line diff is impractical to display.

---

### Custom Component Generator.json

**Changes:** Added `override_skip` and `track_in_telemetry` fields to `context_id`; minor prompt text update.

```diff
diff --git a/src/backend/base/langflow/initial_setup/starter_projects/Custom Component Generator.json b/src/backend/base/langflow/initial_setup/starter_projects/Custom Component Generator.json
index c8f24c41b7..e86ee5e6cf 100644
--- a/src/backend/base/langflow/initial_setup/starter_projects/Custom Component Generator.json
+++ b/src/backend/base/langflow/initial_setup/starter_projects/Custom Component Generator.json
@@ -314,6 +314,7 @@
                 "list_add_label": "Add More",
                 "load_from_db": false,
                 "name": "context_id",
+                "override_skip": false,
                 "placeholder": "",
                 "required": false,
                 "show": true,
@@ -321,6 +322,7 @@
                 "tool_mode": false,
                 "trace_as_input": true,
                 "trace_as_metadata": true,
+                "track_in_telemetry": false,
                 "type": "str",
                 "value": ""
               },
@@ -774,7 +776,7 @@
                 "tool_mode": false,
                 "trace_as_input": true,
                 "type": "prompt",
-                "value": "...Show it in a Markdown code tab...."
+                "value": "...Show it in a Markdown code tab...."
```

> **Note:** The prompt `"value"` change is a single line addition: `"Show it in a Markdown code tab."` was added to the `<component_code>` instruction section. The diff shows the full prompt as a single JSON string line.

---

### Document Q&A.json

**Changes:** File component code_hash updated (embedded File component code updated).

```diff
diff --git a/src/backend/base/langflow/initial_setup/starter_projects/Document Q&A.json b/src/backend/base/langflow/initial_setup/starter_projects/Document Q&A.json
index 10c00d8043..81f020604b 100644
--- a/src/backend/base/langflow/initial_setup/starter_projects/Document Q&A.json
+++ b/src/backend/base/langflow/initial_setup/starter_projects/Document Q&A.json
@@ -1286,7 +1286,7 @@
             "legacy": false,
             "lf_version": "1.4.3",
             "metadata": {
-              "code_hash": "12a5841f1a03",
+              "code_hash": "0d094d664158",
               "dependencies": {
                 "dependencies": [
                   {
@@ -1446,7 +1446,7 @@
                 "show": true,
                 "title_case": false,
                 "type": "code",
-                "value": "<old File component source>"
+                "value": "<updated File component source>"
```

> **Note:** The `"value"` field contains the full File component Python source (~300 lines) as a single JSON string. The change is an update to the embedded File component code (code_hash `12a5841f1a03` -> `0d094d664158`). The actual code changes to the File component are documented in their own feature file.

---

### Instagram Copywriter.json

**Changes:** TextInput legacy marking + model field cleanup.

```diff
diff --git a/src/backend/base/langflow/initial_setup/starter_projects/Instagram Copywriter.json b/src/backend/base/langflow/initial_setup/starter_projects/Instagram Copywriter.json
index dc3f598d51..9608524f5e 100644
--- a/src/backend/base/langflow/initial_setup/starter_projects/Instagram Copywriter.json
+++ b/src/backend/base/langflow/initial_setup/starter_projects/Instagram Copywriter.json
@@ -781,10 +781,10 @@
             ],
             "frozen": false,
             "icon": "type",
-            "legacy": false,
+            "legacy": true,
             "lf_version": "1.0.19.post2",
             "metadata": {
-              "code_hash": "518f16485886",
+              "code_hash": "dea80583c672",
               "dependencies": {
                 "dependencies": [
                   {
@@ -832,7 +832,7 @@
                 "show": true,
                 "title_case": false,
                 "type": "code",
-                "value": "<old TextInput source>"
+                "value": "<updated TextInput source with legacy=True>"
               },
               "input_value": {
                 "_input_type": "MultilineInput",
@@ -2382,7 +2382,6 @@
                 "list_add_label": "Add More",
                 "model_type": "language",
                 "name": "model",
-                "options": [],
                 "override_skip": false,
                 "placeholder": "Setup Provider",
                 "real_time_refresh": true,
@@ -2394,7 +2393,7 @@
                 "trace_as_input": true,
                 "track_in_telemetry": false,
                 "type": "model",
-                "value": []
+                "value": ""
               },
               "n_messages": {
                 "_input_type": "IntInput",
```

---

### Invoice Summarizer.json

**Changes:** Model field cleanup only.

```diff
diff --git a/src/backend/base/langflow/initial_setup/starter_projects/Invoice Summarizer.json b/src/backend/base/langflow/initial_setup/starter_projects/Invoice Summarizer.json
index 5a7e42f0ee..282c67059d 100644
--- a/src/backend/base/langflow/initial_setup/starter_projects/Invoice Summarizer.json
+++ b/src/backend/base/langflow/initial_setup/starter_projects/Invoice Summarizer.json
@@ -1502,7 +1502,6 @@
                 "list_add_label": "Add More",
                 "model_type": "language",
                 "name": "model",
-                "options": [],
                 "override_skip": false,
                 "placeholder": "Setup Provider",
                 "real_time_refresh": true,
@@ -1514,7 +1513,7 @@
                 "trace_as_input": true,
                 "track_in_telemetry": false,
                 "type": "model",
-                "value": []
+                "value": ""
               },
               "n_messages": {
                 "_input_type": "IntInput",
```

---

### Knowledge Ingestion.json

**Changes:** Knowledge Base component code_hash updated (embedded code updated).

```diff
diff --git a/src/backend/base/langflow/initial_setup/starter_projects/Knowledge Ingestion.json b/src/backend/base/langflow/initial_setup/starter_projects/Knowledge Ingestion.json
index f8735b70fe..3b5be4a70d 100644
--- a/src/backend/base/langflow/initial_setup/starter_projects/Knowledge Ingestion.json
+++ b/src/backend/base/langflow/initial_setup/starter_projects/Knowledge Ingestion.json
@@ -742,7 +742,7 @@
             "last_updated": "2025-09-29T18:32:20.563Z",
             "legacy": false,
             "metadata": {
-              "code_hash": "52a451e4f053",
+              "code_hash": "d70806d0794a",
               "dependencies": {
                 "dependencies": [
                   {
@@ -872,7 +872,7 @@
                 "show": true,
                 "title_case": false,
                 "type": "code",
-                "value": "<old Knowledge Base component source>"
+                "value": "<updated Knowledge Base component source>"
```

> **Note:** The `"value"` field contains the full Knowledge Base component Python source as a single JSON string. The change is an update to the embedded code (code_hash `52a451e4f053` -> `d70806d0794a`).

---

### Knowledge Retrieval.json

**Changes:** TextInput legacy marking + Knowledge Base component code update + model field cleanup.

```diff
diff --git a/src/backend/base/langflow/initial_setup/starter_projects/Knowledge Retrieval.json b/src/backend/base/langflow/initial_setup/starter_projects/Knowledge Retrieval.json
index 12edcf289b..cc239c1287 100644
--- a/src/backend/base/langflow/initial_setup/starter_projects/Knowledge Retrieval.json
+++ b/src/backend/base/langflow/initial_setup/starter_projects/Knowledge Retrieval.json
@@ -103,10 +103,10 @@
             ],
             "frozen": false,
             "icon": "type",
-            "legacy": false,
+            "legacy": true,
             "lf_version": "1.5.0.post1",
             "metadata": {
-              "code_hash": "518f16485886",
+              "code_hash": "dea80583c672",
               "dependencies": {
                 "dependencies": [
                   {
@@ -155,7 +155,7 @@
                 "show": true,
                 "title_case": false,
                 "type": "code",
-                "value": "<old TextInput source>"
+                "value": "<updated TextInput source with legacy=True>"
               },
               "input_value": {
                 ...
```

Additional hunks in the same file:

```diff
@@ -1029,7 +1029,7 @@
             "last_updated": "2025-09-29T18:32:20.563Z",
             "legacy": false,
             "metadata": {
-              "code_hash": "52a451e4f053",
+              "code_hash": "d70806d0794a",
```

And the Knowledge Base embedded code value update (code_hash change), plus model field cleanup:

```diff
@@ -1421,7 +1421,6 @@
                 "list_add_label": "Add More",
                 "model_type": "language",
                 "name": "model",
-                "options": [],
                 "override_skip": false,
                 "placeholder": "Setup Provider",
                 "real_time_refresh": true,
@@ -1433,7 +1432,7 @@
                 "trace_as_input": true,
                 "track_in_telemetry": false,
                 "type": "model",
-                "value": []
+                "value": ""
               },
               "n_messages": {
```

> **Note:** This file has 3 types of changes: TextInput legacy marking, Knowledge Base component code update, and model field cleanup. The two embedded code value changes (TextInput and Knowledge Base) contain full Python sources as single JSON strings. Total: 62 insertions(+), 8 deletions(-).

---

### Market Research.json

**Changes:** Model field cleanup only.

```diff
diff --git a/src/backend/base/langflow/initial_setup/starter_projects/Market Research.json b/src/backend/base/langflow/initial_setup/starter_projects/Market Research.json
index 1c64a113fd..7ad997e491 100644
--- a/src/backend/base/langflow/initial_setup/starter_projects/Market Research.json
+++ b/src/backend/base/langflow/initial_setup/starter_projects/Market Research.json
@@ -1507,7 +1507,6 @@
                 "list_add_label": "Add More",
                 "model_type": "language",
                 "name": "model",
-                "options": [],
                 "override_skip": false,
                 "placeholder": "Setup Provider",
                 "real_time_refresh": true,
@@ -1519,7 +1518,7 @@
                 "trace_as_input": true,
                 "track_in_telemetry": false,
                 "type": "model",
-                "value": []
+                "value": ""
               },
               "n_messages": {
                 "_input_type": "IntInput",
```

---

### Meeting Summary.json

**Changes:** Added `override_skip` and `track_in_telemetry` fields to `context_id`.

```diff
diff --git a/src/backend/base/langflow/initial_setup/starter_projects/Meeting Summary.json b/src/backend/base/langflow/initial_setup/starter_projects/Meeting Summary.json
index 8f545864fe..ec27f6e735 100644
--- a/src/backend/base/langflow/initial_setup/starter_projects/Meeting Summary.json
+++ b/src/backend/base/langflow/initial_setup/starter_projects/Meeting Summary.json
@@ -1791,6 +1791,7 @@
                 "list_add_label": "Add More",
                 "load_from_db": false,
                 "name": "context_id",
+                "override_skip": false,
                 "placeholder": "",
                 "required": false,
                 "show": true,
@@ -1798,6 +1799,7 @@
                 "tool_mode": false,
                 "trace_as_input": true,
                 "trace_as_metadata": true,
+                "track_in_telemetry": false,
                 "type": "str",
                 "value": ""
               },
```

---

### Memory Chatbot.json

**Changes:** Added `override_skip` and `track_in_telemetry` fields to `context_id`.

```diff
diff --git a/src/backend/base/langflow/initial_setup/starter_projects/Memory Chatbot.json b/src/backend/base/langflow/initial_setup/starter_projects/Memory Chatbot.json
index 3691d638b6..f39e4c43b5 100644
--- a/src/backend/base/langflow/initial_setup/starter_projects/Memory Chatbot.json
+++ b/src/backend/base/langflow/initial_setup/starter_projects/Memory Chatbot.json
@@ -1002,6 +1002,7 @@
                 "list_add_label": "Add More",
                 "load_from_db": false,
                 "name": "context_id",
+                "override_skip": false,
                 "placeholder": "",
                 "required": false,
                 "show": true,
@@ -1009,6 +1010,7 @@
                 "tool_mode": false,
                 "trace_as_input": true,
                 "trace_as_metadata": true,
+                "track_in_telemetry": false,
                 "type": "str",
                 "value": ""
               },
```

---

### News Aggregator.json

**Changes:** Model field cleanup + Save File component code_hash update.

```diff
diff --git a/src/backend/base/langflow/initial_setup/starter_projects/News Aggregator.json b/src/backend/base/langflow/initial_setup/starter_projects/News Aggregator.json
index 7b4fff7c80..5709f3843d 100644
--- a/src/backend/base/langflow/initial_setup/starter_projects/News Aggregator.json
+++ b/src/backend/base/langflow/initial_setup/starter_projects/News Aggregator.json
@@ -1495,7 +1495,6 @@
                 "list_add_label": "Add More",
                 "model_type": "language",
                 "name": "model",
-                "options": [],
                 "override_skip": false,
                 "placeholder": "Setup Provider",
                 "real_time_refresh": true,
@@ -1507,7 +1506,7 @@
                 "trace_as_input": true,
                 "track_in_telemetry": false,
                 "type": "model",
-                "value": []
+                "value": ""
               },
               "n_messages": {
                 "_input_type": "IntInput",
@@ -1740,7 +1739,7 @@
             "last_updated": "2025-09-30T16:16:26.172Z",
             "legacy": false,
             "metadata": {
-              "code_hash": "6d0e4842271e",
+              "code_hash": "d6b15f91e5d0",
               "dependencies": {
                 "dependencies": [
                   {
@@ -1941,7 +1940,7 @@
                 "show": true,
                 "title_case": false,
                 "type": "code",
-                "value": "<old Save File component source>"
+                "value": "<updated Save File component source>"
```

> **Note:** The Save File component embedded code was updated (code_hash `6d0e4842271e` -> `d6b15f91e5d0`). The `"value"` field contains the full Python source as a single JSON string.

---

### Nvidia Remix.json

**Changes:** Model field cleanup + MCPTools component marked as legacy with code update.

```diff
diff --git a/src/backend/base/langflow/initial_setup/starter_projects/Nvidia Remix.json b/src/backend/base/langflow/initial_setup/starter_projects/Nvidia Remix.json
index 4abdc7fa25..0638a5e824 100644
--- a/src/backend/base/langflow/initial_setup/starter_projects/Nvidia Remix.json
+++ b/src/backend/base/langflow/initial_setup/starter_projects/Nvidia Remix.json
@@ -1127,7 +1127,6 @@
                 "list_add_label": "Add More",
                 "model_type": "language",
                 "name": "model",
-                "options": [],
                 "override_skip": false,
                 "placeholder": "Setup Provider",
                 "real_time_refresh": true,
@@ -1139,7 +1138,7 @@
                 "trace_as_input": true,
                 "track_in_telemetry": false,
                 "type": "model",
-                "value": []
+                "value": ""
               },
               "n_messages": {
                 "_input_type": "IntInput",
@@ -2453,10 +2452,10 @@
             "frozen": false,
             "icon": "Mcp",
             "key": "MCPTools",
-            "legacy": false,
+            "legacy": true,
             "lf_version": "1.4.2",
             "metadata": {
-              "code_hash": "a3700ab467a1",
+              "code_hash": "0439b2703cb8",
               "dependencies": {
                 "dependencies": [
                   {
@@ -2516,7 +2515,7 @@
                 "show": true,
                 "title_case": false,
                 "type": "code",
-                "value": "<old MCPTools component source>"
+                "value": "<updated MCPTools component source with legacy=True>"
```

> **Note:** MCPTools component is marked as legacy (code_hash `a3700ab467a1` -> `0439b2703cb8`). The embedded Python source was updated to include `legacy = True`.

---

### Pokédex Agent.json

**Changes:** Model field cleanup only.

```diff
diff --git a/src/backend/base/langflow/initial_setup/starter_projects/Pokédex Agent.json b/src/backend/base/langflow/initial_setup/starter_projects/Pokédex Agent.json
index 86087cdfde..8c7e9cffd3 100644
--- a/src/backend/base/langflow/initial_setup/starter_projects/Pokédex Agent.json
+++ b/src/backend/base/langflow/initial_setup/starter_projects/Pokédex Agent.json
@@ -1557,7 +1557,6 @@
                 "list_add_label": "Add More",
                 "model_type": "language",
                 "name": "model",
-                "options": [],
                 "override_skip": false,
                 "placeholder": "Setup Provider",
                 "real_time_refresh": true,
@@ -1569,7 +1568,7 @@
                 "trace_as_input": true,
                 "track_in_telemetry": false,
                 "type": "model",
-                "value": []
+                "value": ""
               },
               "n_messages": {
                 "_input_type": "IntInput",
```

---

### Portfolio Website Code Generator.json

**Changes:** TextInput legacy marking + model field cleanup.

```diff
diff --git a/src/backend/base/langflow/initial_setup/starter_projects/Portfolio Website Code Generator.json b/src/backend/base/langflow/initial_setup/starter_projects/Portfolio Website Code Generator.json
index 1b66c48f46..f6af9202cb 100644
--- a/src/backend/base/langflow/initial_setup/starter_projects/Portfolio Website Code Generator.json
+++ b/src/backend/base/langflow/initial_setup/starter_projects/Portfolio Website Code Generator.json
@@ -167,10 +167,10 @@
             "frozen": false,
             "icon": "type",
             "key": "TextInput",
-            "legacy": false,
+            "legacy": true,
             "lf_version": "1.6.0",
             "metadata": {
-              "code_hash": "518f16485886",
+              "code_hash": "dea80583c672",
               "dependencies": {
                 "dependencies": [
                   {
@@ -220,7 +220,7 @@
                 "show": true,
                 "title_case": false,
                 "type": "code",
-                "value": "<old TextInput source>"
+                "value": "<updated TextInput source with legacy=True>"
               },
               ...
```

Additional hunk -- model field cleanup:

```diff
@@ -1264,7 +1264,6 @@
                 "list_add_label": "Add More",
                 "model_type": "language",
                 "name": "model",
-                "options": [],
                 "override_skip": false,
                 "placeholder": "Setup Provider",
                 "real_time_refresh": true,
@@ -1276,7 +1275,7 @@
                 "trace_as_input": true,
                 "track_in_telemetry": false,
                 "type": "model",
-                "value": []
+                "value": ""
               },
               "n_messages": {
```

---

### Price Deal Finder.json

**Changes:** Model field cleanup only.

```diff
diff --git a/src/backend/base/langflow/initial_setup/starter_projects/Price Deal Finder.json b/src/backend/base/langflow/initial_setup/starter_projects/Price Deal Finder.json
index 19d043bf2a..4ff79de43f 100644
--- a/src/backend/base/langflow/initial_setup/starter_projects/Price Deal Finder.json
+++ b/src/backend/base/langflow/initial_setup/starter_projects/Price Deal Finder.json
@@ -1924,7 +1924,6 @@
                 "list_add_label": "Add More",
                 "model_type": "language",
                 "name": "model",
-                "options": [],
                 "override_skip": false,
                 "placeholder": "Setup Provider",
                 "real_time_refresh": true,
@@ -1936,7 +1935,7 @@
                 "trace_as_input": true,
                 "track_in_telemetry": false,
                 "type": "model",
-                "value": []
+                "value": ""
               },
               "n_messages": {
                 "_input_type": "IntInput",
```

---

### Research Agent.json

**Changes:** Model field cleanup only.

```diff
diff --git a/src/backend/base/langflow/initial_setup/starter_projects/Research Agent.json b/src/backend/base/langflow/initial_setup/starter_projects/Research Agent.json
index bb27028f02..1901bf3e8e 100644
--- a/src/backend/base/langflow/initial_setup/starter_projects/Research Agent.json
+++ b/src/backend/base/langflow/initial_setup/starter_projects/Research Agent.json
@@ -3119,7 +3119,6 @@
                 "list_add_label": "Add More",
                 "model_type": "language",
                 "name": "model",
-                "options": [],
                 "override_skip": false,
                 "placeholder": "Setup Provider",
                 "real_time_refresh": true,
@@ -3131,7 +3130,7 @@
                 "trace_as_input": true,
                 "track_in_telemetry": false,
                 "type": "model",
-                "value": []
+                "value": ""
               },
               "n_messages": {
                 "_input_type": "IntInput",
```

---

### SaaS Pricing.json

**Changes:** Model field cleanup only.

```diff
diff --git a/src/backend/base/langflow/initial_setup/starter_projects/SaaS Pricing.json b/src/backend/base/langflow/initial_setup/starter_projects/SaaS Pricing.json
index 54782b901b..25faa1a3ca 100644
--- a/src/backend/base/langflow/initial_setup/starter_projects/SaaS Pricing.json
+++ b/src/backend/base/langflow/initial_setup/starter_projects/SaaS Pricing.json
@@ -1212,7 +1212,6 @@
                 "list_add_label": "Add More",
                 "model_type": "language",
                 "name": "model",
-                "options": [],
                 "override_skip": false,
                 "placeholder": "Setup Provider",
                 "real_time_refresh": true,
@@ -1224,7 +1223,7 @@
                 "trace_as_input": true,
                 "track_in_telemetry": false,
                 "type": "model",
-                "value": []
+                "value": ""
               },
               "n_messages": {
                 "_input_type": "IntInput",
```

---

### Search agent.json

**Changes:** Model field cleanup only.

```diff
diff --git a/src/backend/base/langflow/initial_setup/starter_projects/Search agent.json b/src/backend/base/langflow/initial_setup/starter_projects/Search agent.json
index 109837faae..3f435db2ff 100644
--- a/src/backend/base/langflow/initial_setup/starter_projects/Search agent.json
+++ b/src/backend/base/langflow/initial_setup/starter_projects/Search agent.json
@@ -1263,7 +1263,6 @@
                 "list_add_label": "Add More",
                 "model_type": "language",
                 "name": "model",
-                "options": [],
                 "override_skip": false,
                 "placeholder": "Setup Provider",
                 "real_time_refresh": true,
@@ -1275,7 +1274,7 @@
                 "trace_as_input": true,
                 "track_in_telemetry": false,
                 "type": "model",
-                "value": []
+                "value": ""
               },
               "n_messages": {
                 "_input_type": "IntInput",
```

---

### Sequential Tasks Agents.json

**Changes:** Model field cleanup on 3 Agent components.

```diff
diff --git a/src/backend/base/langflow/initial_setup/starter_projects/Sequential Tasks Agents.json b/src/backend/base/langflow/initial_setup/starter_projects/Sequential Tasks Agents.json
index 665d12b671..391061c0c8 100644
--- a/src/backend/base/langflow/initial_setup/starter_projects/Sequential Tasks Agents.json
+++ b/src/backend/base/langflow/initial_setup/starter_projects/Sequential Tasks Agents.json
@@ -680,7 +680,6 @@
                 "list_add_label": "Add More",
                 "model_type": "language",
                 "name": "model",
-                "options": [],
                 "override_skip": false,
                 "placeholder": "Setup Provider",
                 "real_time_refresh": true,
@@ -692,7 +691,7 @@
                 "trace_as_input": true,
                 "track_in_telemetry": false,
                 "type": "model",
-                "value": []
+                "value": ""
               },
               "n_messages": {
                 "_input_type": "IntInput",
@@ -1260,7 +1259,6 @@
                 "list_add_label": "Add More",
                 "model_type": "language",
                 "name": "model",
-                "options": [],
                 "override_skip": false,
                 "placeholder": "Setup Provider",
                 "real_time_refresh": true,
@@ -1272,7 +1270,7 @@
                 "trace_as_input": true,
                 "track_in_telemetry": false,
                 "type": "model",
-                "value": []
+                "value": ""
               },
               "n_messages": {
                 "_input_type": "IntInput",
@@ -2693,7 +2691,6 @@
                 "list_add_label": "Add More",
                 "model_type": "language",
                 "name": "model",
-                "options": [],
                 "override_skip": false,
                 "placeholder": "Setup Provider",
                 "real_time_refresh": true,
@@ -2705,7 +2702,7 @@
                 "trace_as_input": true,
                 "track_in_telemetry": false,
                 "type": "model",
-                "value": []
+                "value": ""
               },
               "n_messages": {
                 "_input_type": "IntInput",
```

---

### Simple Agent.json

**Changes:** Model field cleanup only.

```diff
diff --git a/src/backend/base/langflow/initial_setup/starter_projects/Simple Agent.json b/src/backend/base/langflow/initial_setup/starter_projects/Simple Agent.json
index 4329443f7f..5912b48dbb 100644
--- a/src/backend/base/langflow/initial_setup/starter_projects/Simple Agent.json
+++ b/src/backend/base/langflow/initial_setup/starter_projects/Simple Agent.json
@@ -1253,7 +1253,6 @@
                 "list_add_label": "Add More",
                 "model_type": "language",
                 "name": "model",
-                "options": [],
                 "override_skip": false,
                 "placeholder": "Setup Provider",
                 "real_time_refresh": true,
@@ -1265,7 +1264,7 @@
                 "trace_as_input": true,
                 "track_in_telemetry": false,
                 "type": "model",
-                "value": []
+                "value": ""
               },
               "n_messages": {
                 "_input_type": "IntInput",
```

---

### Social Media Agent.json

**Changes:** Model field cleanup only.

```diff
diff --git a/src/backend/base/langflow/initial_setup/starter_projects/Social Media Agent.json b/src/backend/base/langflow/initial_setup/starter_projects/Social Media Agent.json
index 5755e473d6..7698e9a07c 100644
--- a/src/backend/base/langflow/initial_setup/starter_projects/Social Media Agent.json
+++ b/src/backend/base/langflow/initial_setup/starter_projects/Social Media Agent.json
@@ -1611,7 +1611,6 @@
                 "list_add_label": "Add More",
                 "model_type": "language",
                 "name": "model",
-                "options": [],
                 "override_skip": false,
                 "placeholder": "Setup Provider",
                 "real_time_refresh": true,
@@ -1623,7 +1622,7 @@
                 "trace_as_input": true,
                 "track_in_telemetry": false,
                 "type": "model",
-                "value": []
+                "value": ""
               },
               "n_messages": {
                 "_input_type": "IntInput",
```

---

### Text Sentiment Analysis.json

**Changes:** File component code_hash updated (embedded code updated).

```diff
diff --git a/src/backend/base/langflow/initial_setup/starter_projects/Text Sentiment Analysis.json b/src/backend/base/langflow/initial_setup/starter_projects/Text Sentiment Analysis.json
index 108e2bbabb..2c9df41a2a 100644
--- a/src/backend/base/langflow/initial_setup/starter_projects/Text Sentiment Analysis.json
+++ b/src/backend/base/langflow/initial_setup/starter_projects/Text Sentiment Analysis.json
@@ -2585,7 +2585,7 @@
             "icon": "file-text",
             "legacy": false,
             "metadata": {
-              "code_hash": "12a5841f1a03",
+              "code_hash": "0d094d664158",
               "dependencies": {
                 "dependencies": [
                   {
@@ -2745,7 +2745,7 @@
                 "show": true,
                 "title_case": false,
                 "type": "code",
-                "value": "<old File component source>"
+                "value": "<updated File component source>"
```

> **Note:** Same File component code update as Document Q&A (code_hash `12a5841f1a03` -> `0d094d664158`).

---

### Travel Planning Agents.json

**Changes:** Model field cleanup on 3 Agent components.

```diff
diff --git a/src/backend/base/langflow/initial_setup/starter_projects/Travel Planning Agents.json b/src/backend/base/langflow/initial_setup/starter_projects/Travel Planning Agents.json
index a996699f7f..a7365885db 100644
--- a/src/backend/base/langflow/initial_setup/starter_projects/Travel Planning Agents.json
+++ b/src/backend/base/langflow/initial_setup/starter_projects/Travel Planning Agents.json
@@ -1981,7 +1981,6 @@
                 "list_add_label": "Add More",
                 "model_type": "language",
                 "name": "model",
-                "options": [],
                 "override_skip": false,
                 "placeholder": "Setup Provider",
                 "real_time_refresh": true,
@@ -1993,7 +1992,7 @@
                 "trace_as_input": true,
                 "track_in_telemetry": false,
                 "type": "model",
-                "value": []
+                "value": ""
               },
               "n_messages": {
                 "_input_type": "IntInput",
@@ -2556,7 +2555,6 @@
                 "list_add_label": "Add More",
                 "model_type": "language",
                 "name": "model",
-                "options": [],
                 "override_skip": false,
                 "placeholder": "Setup Provider",
                 "real_time_refresh": true,
@@ -2568,7 +2566,7 @@
                 "trace_as_input": true,
                 "track_in_telemetry": false,
                 "type": "model",
-                "value": []
+                "value": ""
               },
               "n_messages": {
                 "_input_type": "IntInput",
@@ -3131,7 +3129,6 @@
                 "list_add_label": "Add More",
                 "model_type": "language",
                 "name": "model",
-                "options": [],
                 "override_skip": false,
                 "placeholder": "Setup Provider",
                 "real_time_refresh": true,
@@ -3143,7 +3140,7 @@
                 "trace_as_input": true,
                 "track_in_telemetry": false,
                 "type": "model",
-                "value": []
+                "value": ""
               },
               "n_messages": {
                 "_input_type": "IntInput",
```

---

### Twitter Thread Generator.json

**Changes:** TextInput legacy marking on 6 TextInput instances. All follow the same pattern.

```diff
diff --git a/src/backend/base/langflow/initial_setup/starter_projects/Twitter Thread Generator.json b/src/backend/base/langflow/initial_setup/starter_projects/Twitter Thread Generator.json
index 3a4b0a205a..01189c706c 100644
--- a/src/backend/base/langflow/initial_setup/starter_projects/Twitter Thread Generator.json
+++ b/src/backend/base/langflow/initial_setup/starter_projects/Twitter Thread Generator.json
```

Instance 1 (line ~553):
```diff
@@ -553,10 +553,10 @@
             ],
             "frozen": false,
             "icon": "type",
-            "legacy": false,
+            "legacy": true,
             "lf_version": "1.0.19.post2",
             "metadata": {
-              "code_hash": "518f16485886",
+              "code_hash": "dea80583c672",
```

Instance 2 (line ~977):
```diff
@@ -977,10 +977,10 @@
             ],
             "frozen": false,
             "icon": "type",
-            "legacy": false,
+            "legacy": true,
             "lf_version": "1.0.19.post2",
             "metadata": {
-              "code_hash": "518f16485886",
+              "code_hash": "dea80583c672",
```

Instance 3 (line ~1113):
```diff
@@ -1113,10 +1113,10 @@
             ],
             "frozen": false,
             "icon": "type",
-            "legacy": false,
+            "legacy": true,
             "lf_version": "1.0.19.post2",
             "metadata": {
-              "code_hash": "518f16485886",
+              "code_hash": "dea80583c672",
```

Instance 4 (line ~1249):
```diff
@@ -1249,10 +1249,10 @@
             ],
             "frozen": false,
             "icon": "type",
-            "legacy": false,
+            "legacy": true,
             "lf_version": "1.0.19.post2",
             "metadata": {
-              "code_hash": "518f16485886",
+              "code_hash": "dea80583c672",
```

Instance 5 (line ~1385):
```diff
@@ -1385,10 +1385,10 @@
             ],
             "frozen": false,
             "icon": "type",
-            "legacy": false,
+            "legacy": true,
             "lf_version": "1.0.19.post2",
             "metadata": {
-              "code_hash": "518f16485886",
+              "code_hash": "dea80583c672",
```

Instance 6 (line ~1521):
```diff
@@ -1521,10 +1521,10 @@
             ],
             "frozen": false,
             "icon": "type",
-            "legacy": false,
+            "legacy": true,
             "lf_version": "1.0.19.post2",
             "metadata": {
-              "code_hash": "518f16485886",
+              "code_hash": "dea80583c672",
```

> **Note:** Each instance also has a `"value"` code string update (TextInput source with `legacy = True` and `replacement` added). The pattern is identical across all 6 instances. The embedded code value diffs are omitted as each is a full Python source on a single JSON line.

---

### Vector Store RAG.json

**Changes:** File component code_hash updated (embedded code updated).

```diff
diff --git a/src/backend/base/langflow/initial_setup/starter_projects/Vector Store RAG.json b/src/backend/base/langflow/initial_setup/starter_projects/Vector Store RAG.json
index 7406705e45..05d4bf8ffe 100644
--- a/src/backend/base/langflow/initial_setup/starter_projects/Vector Store RAG.json
+++ b/src/backend/base/langflow/initial_setup/starter_projects/Vector Store RAG.json
@@ -2693,7 +2693,7 @@
             "last_updated": "2025-10-10T17:51:29.596Z",
             "legacy": false,
             "metadata": {
-              "code_hash": "12a5841f1a03",
+              "code_hash": "0d094d664158",
               "dependencies": {
                 "dependencies": [
                   {
@@ -2853,7 +2853,7 @@
                 "show": true,
                 "title_case": false,
                 "type": "code",
-                "value": "<old File component source>"
+                "value": "<updated File component source>"
```

> **Note:** Same File component code update as Document Q&A and Text Sentiment Analysis (code_hash `12a5841f1a03` -> `0d094d664158`).

---

### Youtube Analysis.json

**Changes:** YouTube Comments component code update + model field cleanup (largest diff: removed hardcoded model options).

```diff
diff --git a/src/backend/base/langflow/initial_setup/starter_projects/Youtube Analysis.json b/src/backend/base/langflow/initial_setup/starter_projects/Youtube Analysis.json
index 1efd237451..3bd78a53f8 100644
--- a/src/backend/base/langflow/initial_setup/starter_projects/Youtube Analysis.json
+++ b/src/backend/base/langflow/initial_setup/starter_projects/Youtube Analysis.json
@@ -230,7 +230,7 @@
             "legacy": false,
             "lf_version": "1.4.3",
             "metadata": {
-              "code_hash": "20398e0d18df",
+              "code_hash": "8c5296516f6c",
               "dependencies": {
```

YouTube Comments component embedded code update (code_hash `20398e0d18df` -> `8c5296516f6c`):

```diff
@@ -305,7 +305,7 @@
                 "show": true,
                 "title_case": false,
                 "type": "code",
-                "value": "<old YouTube Comments source>"
+                "value": "<updated YouTube Comments source>"
```

> **Note:** The YouTube Comments component code change fixes the empty comments case -- it now checks `if not comments_data` and creates an empty DataFrame with proper columns instead of trying to operate on an empty list.

Model field cleanup -- **this is the largest structural change in the feature**, removing 149 lines of hardcoded model options:

```diff
@@ -790,155 +790,6 @@
                 "list_add_label": "Add More",
                 "model_type": "language",
                 "name": "model",
-                "options": [
-                  {
-                    "category": "Anthropic",
-                    "icon": "Anthropic",
-                    "metadata": {
-                      "api_key_param": "api_key",
-                      "context_length": 128000,
-                      "model_class": "ChatAnthropic",
-                      "model_name_param": "model"
-                    },
-                    "name": "claude-opus-4-5-20251101",
-                    "provider": "Anthropic"
-                  },
-                  {
-                    "category": "Anthropic",
-                    "icon": "Anthropic",
-                    "metadata": { ... },
-                    "name": "claude-haiku-4-5-20251001",
-                    "provider": "Anthropic"
-                  },
-                  {
-                    "category": "Anthropic",
-                    "icon": "Anthropic",
-                    "metadata": { ... },
-                    "name": "claude-sonnet-4-5-20250929",
-                    "provider": "Anthropic"
-                  },
-                  {
-                    "category": "Anthropic",
-                    "icon": "Anthropic",
-                    "metadata": { ... },
-                    "name": "claude-opus-4-1-20250805",
-                    "provider": "Anthropic"
-                  },
-                  {
-                    "category": "Anthropic",
-                    "icon": "Anthropic",
-                    "metadata": { ... },
-                    "name": "claude-opus-4-20250514",
-                    "provider": "Anthropic"
-                  },
-                  {
-                    "category": "OpenAI",
-                    "icon": "OpenAI",
-                    "metadata": { ... },
-                    "name": "gpt-5",
-                    "provider": "OpenAI"
-                  },
-                  {
-                    "category": "OpenAI",
-                    "icon": "OpenAI",
-                    "metadata": { ... },
-                    "name": "gpt-5-mini",
-                    "provider": "OpenAI"
-                  },
-                  {
-                    "category": "OpenAI",
-                    "icon": "OpenAI",
-                    "metadata": { ... },
-                    "name": "gpt-5-nano",
-                    "provider": "OpenAI"
-                  },
-                  {
-                    "category": "OpenAI",
-                    "icon": "OpenAI",
-                    "metadata": { ... },
-                    "name": "gpt-4o-mini",
-                    "provider": "OpenAI"
-                  },
-                  {
-                    "category": "Google Generative AI",
-                    "icon": "GoogleGenerativeAI",
-                    "metadata": { "is_disabled_provider": true, ... },
-                    "name": "__enable_provider_Google Generative AI__",
-                    "provider": "Google Generative AI"
-                  },
-                  {
-                    "category": "Ollama",
-                    "icon": "Ollama",
-                    "metadata": { "is_disabled_provider": true, ... },
-                    "name": "__enable_provider_Ollama__",
-                    "provider": "Ollama"
-                  },
-                  {
-                    "category": "IBM WatsonX",
-                    "icon": "WatsonxAI",
-                    "metadata": { "is_disabled_provider": true, ... },
-                    "name": "__enable_provider_IBM WatsonX__",
-                    "provider": "IBM WatsonX"
-                  }
-                ],
                 "override_skip": false,
                 "placeholder": "Setup Provider",
```

And the value change from a selected model object to empty string:

```diff
@@ -950,20 +801,7 @@
                 "trace_as_input": true,
                 "track_in_telemetry": false,
                 "type": "model",
-                "value": [
-                  {
-                    "category": "Anthropic",
-                    "icon": "Anthropic",
-                    "metadata": {
-                      "api_key_param": "api_key",
-                      "context_length": 128000,
-                      "model_class": "ChatAnthropic",
-                      "model_name_param": "model"
-                    },
-                    "name": "claude-opus-4-5-20251101",
-                    "provider": "Anthropic"
-                  }
-                ]
+                "value": ""
               },
               "n_messages": {
                 "_input_type": "IntInput",
```

> **Note:** Youtube Analysis had the most extensive model field cleanup because it had hardcoded model options (Anthropic claude-opus-4-5, claude-haiku-4-5, claude-sonnet-4-5, claude-opus-4-1, claude-opus-4, OpenAI gpt-5/mini/nano, gpt-4o-mini, plus disabled providers Google, Ollama, IBM WatsonX) and a pre-selected value (claude-opus-4-5). All of this was removed, leaving model options to be populated dynamically.

---

## Change Summary by Category

| Category | Files |
|----------|-------|
| **Model field cleanup only** (`options`/`value` removal) | Invoice Summarizer, Market Research, Pokédex Agent, Price Deal Finder, Research Agent, SaaS Pricing, Search agent, Simple Agent, Social Media Agent |
| **Model field cleanup (multiple agents)** | Sequential Tasks Agents (3x), Travel Planning Agents (3x) |
| **TextInput legacy marking only** | Blog Writer |
| **TextInput legacy + model cleanup** | Instagram Copywriter, Knowledge Retrieval, Portfolio Website Code Generator |
| **TextInput legacy (multiple instances)** | Twitter Thread Generator (6x) |
| **Embedded component code update only** | Document Q&A (File), Knowledge Ingestion (KB), Text Sentiment Analysis (File), Vector Store RAG (File) |
| **Embedded code update + model cleanup** | News Aggregator (Save File), Nvidia Remix (MCPTools), Youtube Analysis (YouTube Comments + full options removal) |
| **Model input_types cleanup** | Basic Prompting |
| **context_id field additions** | Custom Component Generator, Meeting Summary, Memory Chatbot |
