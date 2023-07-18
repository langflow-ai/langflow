# Latest Changes

🎉 We're thrilled to announce our latest release, packed with exciting updates and improvements to enhance your experience. Here's what you can look forward to:

<br>
🪄 Interface Updates

<br>
💫 New Components & Enhancements

<br>
⌨️ Code Refactoring & Optimization

<br>
🐛 A range of updates and bug fixes!

<br>
We're constantly striving to improve our platform and provide you with the best tools and features. Stay tuned for more updates as we continue to evolve and meet your needs. Thank you for being a part of our journey! ✨🚀

## v0.0.79

### What's Changed
* hot fix for dinamic size of font for buttonBox component by @anovazzi1 in https://github.com/logspace-ai/langflow/pull/337
* add useEffect to prevent chat lock on fail of onClose method by @anovazzi1 in https://github.com/logspace-ai/langflow/pull/342
* Hotfix for Import Flows modal by @lucaseduoli in https://github.com/logspace-ai/langflow/pull/357
* fix crash when upload large file, not saving files on browser storage by @anovazzi1 in https://github.com/logspace-ai/langflow/pull/362
* Refactor Vector stores creator to help implementing others by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/365
* 🔨 refactor(base.py): refactor FrontendNode.format_field() method to improve readability and maintainability by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/363
* Changes to accomodate new vector stores by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/366
* fix: SQLAgent by @gabfr in https://github.com/logspace-ai/langflow/pull/370
* Add First Version of Generic Modal Input Model by @Cristhianzl in https://github.com/logspace-ai/langflow/pull/369
* Activating HuggingFaceEmbeddings, adding Jina deps by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/378
* Hotfix: fix bug on refresh and and for sending files to backend by @anovazzi1 in https://github.com/logspace-ai/langflow/pull/384
* feat: notion directory loader by @gabfr in https://github.com/logspace-ai/langflow/pull/382
* Error Handling for Modal Calls in Different Flows Prompt/Text by @Cristhianzl in https://github.com/logspace-ai/langflow/pull/390
* Add Cohere LLM by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/388
* Pull Request: UI Feature Enhancements by @Cristhianzl in https://github.com/logspace-ai/langflow/pull/393
* Revert "Add Cohere LLM" by @gustavoschaedler in https://github.com/logspace-ai/langflow/pull/394
* Adding support for Ctransformers by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/387
* 🚀 feat(langflow): add support for extra fields in VectorStoreFrontendNode by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/396
* Add Cohere LLM by @gustavoschaedler in https://github.com/logspace-ai/langflow/pull/397
* Adding scrollbar on overflow itens modal by @Cristhianzl in https://github.com/logspace-ai/langflow/pull/400
* feat: SlackDirectoryLoader by @gabfr in https://github.com/logspace-ai/langflow/pull/383
* Add Icons module by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/368
* Added format_instructions to ZeroShotPrompt by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/402
* added custom icon pack for special cases  by @anovazzi1 in https://github.com/logspace-ai/langflow/pull/405
* UI Improvements: tooltip, classes icons e icons by @Cristhianzl in https://github.com/logspace-ai/langflow/pull/404
* New LLMs, Embeddings and UI improvements by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/407

#### New Contributors
* @gabfr made their first contribution in https://github.com/logspace-ai/langflow/pull/370
* @Cristhianzl made their first contribution in https://github.com/logspace-ai/langflow/pull/369
* @gustavoschaedler made their first contribution in https://github.com/logspace-ai/langflow/pull/394

**Full Changelog**: https://github.com/logspace-ai/langflow/compare/v0.0.78...v0.0.79

## v0.0.78

### What's Changed

- Hotfix: remove deepcopy, fixes llm rebuilding by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/349
- Hotfix: Deepcopy removal and bump to 0.0.77 by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/350
- 🔖 chore(pyproject.toml): bump version to 0.0.78 by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/351

**Full Changelog**: https://github.com/logspace-ai/langflow/compare/v0.0.76...v0.0.78

## v0.0.77

### What's Changed

- ci: test lcserve push job by @deepankarm in https://github.com/logspace-ai/langflow/pull/333
- Hotfix: Chroma does not raise NotEnoughElementsException anymore by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/334

**Full Changelog**: https://github.com/logspace-ai/langflow/compare/v0.0.75...v0.0.77

## v0.0.76

### What's Changed

- ci: test lcserve push job by @deepankarm in https://github.com/logspace-ai/langflow/pull/333
- Hotfix: Chroma does not raise NotEnoughElementsException anymore by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/334

**Full Changelog**: https://github.com/logspace-ai/langflow/compare/v0.0.75...v0.0.76

## v0.0.75

### What's Changed

- migrating to Vite by @gsaivinay in https://github.com/logspace-ai/langflow/pull/287
- fix: duplicated lodash by @Dogtiti in https://github.com/logspace-ai/langflow/pull/293
- Hotfix: Save Flow Bug in Browser by @anovazzi1 in https://github.com/logspace-ai/langflow/pull/304
- Update llama-cpp-python version in pyproject.toml by @phyyou in https://github.com/logspace-ai/langflow/pull/299
- Address issue #300 - GCP Shell Script - Websocket Connection Failure by @genome21 in https://github.com/logspace-ai/langflow/pull/301
- Add health check endpoint by @filipecaixeta in https://github.com/logspace-ai/langflow/pull/311
- Hotfixes: Dark Mode classes and Text Wrapper by @lucaseduoli in https://github.com/logspace-ai/langflow/pull/309
- Validation_fix by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/317
- feat: deploy langflow using langchain-serve by @deepankarm in https://github.com/logspace-ai/langflow/pull/307
- chore: lint fix by @deepankarm in https://github.com/logspace-ai/langflow/pull/320
- Retry_get_all by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/324
- node updating template, base classes and description by @anovazzi1 in https://github.com/logspace-ai/langflow/pull/326
- Add New Features and Improvements by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/329

#### New Contributors

- @gsaivinay made their first contribution in https://github.com/logspace-ai/langflow/pull/287
- @Dogtiti made their first contribution in https://github.com/logspace-ai/langflow/pull/293
- @phyyou made their first contribution in https://github.com/logspace-ai/langflow/pull/299
- @filipecaixeta made their first contribution in https://github.com/logspace-ai/langflow/pull/311
- @deepankarm made their first contribution in https://github.com/logspace-ai/langflow/pull/307

**Full Changelog**: https://github.com/logspace-ai/langflow/compare/v0.0.74...v0.0.75

## v0.0.74

### What's Changed

- Hotfix: saving flow in the browser local storage by @anovazzi1 in https://github.com/logspace-ai/langflow/pull/315

**Full Changelog**: https://github.com/logspace-ai/langflow/compare/v0.0.73...v0.0.74

## v0.0.73

### What's Changed

- Hotfix: Save Flow Bug in Browser by @anovazzi1 in https://github.com/logspace-ai/langflow/pull/305
- updated pyproject version by @anovazzi1 in https://github.com/logspace-ai/langflow/pull/306

**Full Changelog**: https://github.com/logspace-ai/langflow/compare/v0.0.72...v0.0.73

## v0.0.72

### What's Changed

- Hotfix: api code in api button was missing an import by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/303

**Full Changelog**: https://github.com/logspace-ai/langflow/compare/v0.0.71...v0.0.72

## v0.0.71

### What's Changed

- refactor(loading.py): change instantiate_prompt function signature to include class_object parameter and use it to instantiate the prompt object by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/302

**Full Changelog**: https://github.com/logspace-ai/langflow/compare/v0.0.70...v0.0.71

## v0.0.70

### What's Changed

- Hotfix: Temporary fix for intermediate steps by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/295

**Full Changelog**: https://github.com/logspace-ai/langflow/compare/v0.0.69...v0.0.70

## v0.0.69

### What's Changed

- disable password copy by @CodeAunt in https://github.com/logspace-ai/langflow/pull/224
- Fix auto update by @anovazzi1 in https://github.com/logspace-ai/langflow/pull/238
- UI improvements by @anovazzi1 in https://github.com/logspace-ai/langflow/pull/240
- Hot fixes by @anovazzi1 in https://github.com/logspace-ai/langflow/pull/244
- Tool_fixes by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/258
- Better_predict by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/267
- change line endings to linux. by @bobsburgers in https://github.com/logspace-ai/langflow/pull/254
- Copy Paste, Undo and Redo implemented by @lucaseduoli in https://github.com/logspace-ai/langflow/pull/253
- Streaming, Chat Markdown, and CacheManager by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/282
- Dark Mode and API Modal by @lucaseduoli in https://github.com/logspace-ai/langflow/pull/284
- fixed copy and paste bug by @anovazzi1 in https://github.com/logspace-ai/langflow/pull/286
- Websocket, cache_manager, API access, Dark mode fixes by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/285

#### New Contributors

- @CodeAunt made their first contribution in https://github.com/logspace-ai/langflow/pull/224
- @bobsburgers made their first contribution in https://github.com/logspace-ai/langflow/pull/254

**Full Changelog**: https://github.com/logspace-ai/langflow/compare/v0.0.68...v0.0.69

---

## v0.0.68

### Highlights

:sparkles: Release: Chat and Cache Improvements, Websocket Integration, and Dark Mode Enhancements :crescent_moon:
This release brings a series of new features and improvements, including:

- :speech_balloon: Chat and Cache Improvements:
  - Refactored cache-related functions and moved them to a new base.py module
  - Simplified the Chat component and added chat history support
  - Implemented the ability to send file responses in chat
  - Real-time Node validation for improved user experience
  - CacheManager was added to share data between tools and display them in the chat.
- :globe_with_meridians: Websocket Integration:
  - Implemented websocket connection for the chat (WIP)
- :crescent_moon: Dark Mode Enhancements:
  - Fixed dark mode for dropdown components
  - Improved dark mode styling for the chat interface
  - Updated thought icon for dark mode
- :rocket: Other Improvements:
  - Migrated chat logic to chat modal
  - Implemented unique IDs for flow management
  - Sorted sidebar items for better organization
  - Removed unused imports and optimized codebase

### What's Changed

- refactor(loading.py): use get method to set allowed_tools to an empty list if it is not present in params dictionary by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/237

**Full Changelog**: https://github.com/logspace-ai/langflow/compare/v0.0.67...v0.0.68

## v0.0.67

### What's Changed

- Fix to allowed_tools by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/235

**Full Changelog**: https://github.com/logspace-ai/langflow/compare/v0.0.66...v0.0.67

## v0.0.66

### What's Changed

- Hotfix to websocket url by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/234

**Full Changelog**: https://github.com/logspace-ai/langflow/compare/v0.0.65...v0.0.66

## v0.0.65

### What's Changed

- Hotfix by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/231

**Full Changelog**: https://github.com/logspace-ai/langflow/compare/v0.0.64...v0.0.65

## v0.0.64

### What's Changed

- Fix LangChain imports by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/229
- fix tests to comply with updates and hotfixes by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/230

**Full Changelog**: https://github.com/logspace-ai/langflow/compare/v0.0.63...v0.0.64

## v0.0.63

### What's Changed

- Layout hotfixes by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/223

**Full Changelog**: https://github.com/logspace-ai/langflow/compare/v0.0.62...v0.0.63

## v0.0.62

### What's Changed

- Hotfix bug on import from local by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/222

**Full Changelog**: https://github.com/logspace-ai/langflow/compare/v0.0.61...v0.0.62

## v0.0.61

### What's Changed

- refactor(validate.py): extract build_graph function to langflow.inter… by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/204
- Update LangChain version by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/211
- Update the Semver Specifier for `langchain` to allow for all <0.1.0 versions. by @darthtrevino in https://github.com/logspace-ai/langflow/pull/86
- feat: add demo devcontainer by @aaronsteers in https://github.com/logspace-ai/langflow/pull/201
- Node modal by @anovazzi1 in https://github.com/logspace-ai/langflow/pull/174
- Auto update nodes by @anovazzi1 in https://github.com/logspace-ai/langflow/pull/218
- Chat_and_cache by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/219
- :sparkles: Release: Chat and Cache Improvements, Websocket Integration, and Dark Mode Enhancements :crescent_moon: by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/220

#### New Contributors

- @darthtrevino made their first contribution in https://github.com/logspace-ai/langflow/pull/86
- @aaronsteers made their first contribution in https://github.com/logspace-ai/langflow/pull/201

**Full Changelog**: https://github.com/logspace-ai/langflow/compare/v0.0.58...v0.0.61

## v0.0.58

### What's Changed

- Fix bug when running LLM alone by @ibiscp in https://github.com/logspace-ai/langflow/pull/160
- Refactor tools by @ibiscp in https://github.com/logspace-ai/langflow/pull/176
- load_flow_from_json("path/to/flow.json") returns UnicodeDecodeError by @bigKeter in https://github.com/logspace-ai/langflow/pull/165
- Create a VM in a GCP project that serves the Langflow app by @genome21 in https://github.com/logspace-ai/langflow/pull/169
- Correct run instructions in Readme by @PaulLockett in https://github.com/logspace-ai/langflow/pull/87
- Add Import Examples Feature to Flow Editor by @anovazzi1 in https://github.com/logspace-ai/langflow/pull/175
- Change button placement by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/193
- API keys for LLMs and Embeddings are now loaded from env if available by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/195
- style(langflow): fix formatting and add type hinting to custom.py and run.py files by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/194
- Example loader and bugfixes by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/199

#### New Contributors

- @bigKeter made their first contribution in https://github.com/logspace-ai/langflow/pull/165
- @genome21 made their first contribution in https://github.com/logspace-ai/langflow/pull/169
- @PaulLockett made their first contribution in https://github.com/logspace-ai/langflow/pull/87

## v0.0.57

### What's Changed

- Hotfix: psygopg2 might break installation by @ogabrielluiz in #168

## v0.0.56

### What's Changed

- Add contrib link to readme by @jacobhrussell in https://github.com/logspace-ai/langflow/pull/136
- Llama Support by @yoazmenda in https://github.com/logspace-ai/langflow/pull/134
- feat: added LLMFrontendNode by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/140
- Firefox password by @anovazzi1 in https://github.com/logspace-ai/langflow/pull/147
- removable edges implemented by @anovazzi1 in https://github.com/logspace-ai/langflow/pull/149
- Vector stores, embeddings, document loaders, and text splitters by @ibiscp in https://github.com/logspace-ai/langflow/pull/145
- Adding new fields to Chain nodes by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/148
- Add new docloaders and change the way files are loaded by @ibiscp in https://github.com/logspace-ai/langflow/pull/154
- Change docstring parser by @ibiscp in https://github.com/logspace-ai/langflow/pull/158
- Add SQL Agent by @ibiscp in https://github.com/logspace-ai/langflow/pull/159
- VectorStores, DocumentLoaders, TextSplitters, Embeddings and other additions by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/157

#### New Contributors

- @jacobhrussell made their first contribution in https://github.com/logspace-ai/langflow/pull/136
- @yoazmenda made their first contribution in https://github.com/logspace-ai/langflow/pull/134

**Full Changelog**: https://github.com/logspace-ai/langflow/compare/v0.0.55...v0.0.56

## v0.0.55

### What's Changed

- feat: chain template tests by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/125
- feat: adding prompt template tests by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/128
- feat: added agents tests by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/127
- refact: more maintable build_nodes by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/123
- Modifies frontend chatComponent to itemize validation errors by @cayal in https://github.com/logspace-ai/langflow/pull/126
- add minor fix for required fields that are not displayed by @anovazzi1 in https://github.com/logspace-ai/langflow/pull/129
- feat: added first tests for llms by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/130
- Update CONTRIBUTING.md by @jordi-adame in https://github.com/logspace-ai/langflow/pull/133
- Fixes to ChainCreator and PromptTemplate processing by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/135
- Fix tool bug by @ibiscp in https://github.com/logspace-ai/langflow/pull/137
- Fix bugs, add tests, and refactor code by @ibiscp in https://github.com/logspace-ai/langflow/pull/138

#### New Contributors

- @cayal made their first contribution in https://github.com/logspace-ai/langflow/pull/126
- @jordi-adame made their first contribution in https://github.com/logspace-ai/langflow/pull/133

**Full Changelog**: https://github.com/logspace-ai/langflow/compare/v0.0.54...v0.0.55

## v0.0.54

### What's Changed

- Remove tools until fixed by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/124
- Fix prompt validation exception condition by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/122

**Full Changelog**: https://github.com/logspace-ai/langflow/compare/v0.0.53...v0.0.54

## v0.0.53

### What's Changed

- Implementation of Agents as Tools and Custom Tools by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/79
- removed handle from code component by @anovazzi1 in https://github.com/logspace-ai/langflow/pull/83
- refac: Factory implementation of LangChainTypes by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/84
- Toolkits by @ibiscp in https://github.com/logspace-ai/langflow/pull/92
- Added initialize_agent and Memory by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/93
- fix: deactivate intermediate steps for now by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/97
- Chain loader by @ibiscp in https://github.com/logspace-ai/langflow/pull/98
- UI fixes by @anovazzi1 in https://github.com/logspace-ai/langflow/pull/99
- colorized think with ANSI to HTML by @anovazzi1 in https://github.com/logspace-ai/langflow/pull/101
- bug fixed when not implemented nodes are imported to the flow by @anovazzi1 in https://github.com/logspace-ai/langflow/pull/102
- delete the message that was sent when the backend returned an error by @anovazzi1 in https://github.com/logspace-ai/langflow/pull/105
- fixed validation error by @anovazzi1 in https://github.com/logspace-ai/langflow/pull/106
- Implement Memories, validation and other fixes by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/107
- fix: adding memory node and better exceptions by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/110
- UI improvements by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/112
- Bug fixes by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/115
- Ui improvement by @anovazzi1 in https://github.com/logspace-ai/langflow/pull/114
- Prompt component by @anovazzi1 in https://github.com/logspace-ai/langflow/pull/116
- added colors to toolkits and wrappers by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/118

**Full Changelog**: https://github.com/logspace-ai/langflow/compare/v0.0.46...v0.0.53

## v0.0.52

### What's Changed

- fix: adding maintainers and other configs by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/59
- feat: added constants file to support model types and others by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/60
- UI updates by @anovazzi1 in https://github.com/logspace-ai/langflow/pull/63
- full dropdown clickable by @anovazzi1 in https://github.com/logspace-ai/langflow/pull/69
- Add config file with option to enable all features by @ibiscp in https://github.com/logspace-ai/langflow/pull/70
- UI updates by @anovazzi1 in https://github.com/logspace-ai/langflow/pull/71
- Release 0.0.46 by @ibiscp in https://github.com/logspace-ai/langflow/pull/77
- Release 0.0.46 by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/78

**Full Changelog**: https://github.com/logspace-ai/langflow/compare/v0.0.45...v0.0.52

## v0.0.46

### What's Changed

- fix: adding maintainers and other configs by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/59
- feat: added constants file to support model types and others by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/60
- UI updates by @anovazzi1 in https://github.com/logspace-ai/langflow/pull/63
- full dropdown clickable by @anovazzi1 in https://github.com/logspace-ai/langflow/pull/69
- Add config file with option to enable all features by @ibiscp in https://github.com/logspace-ai/langflow/pull/70
- UI updates by @anovazzi1 in https://github.com/logspace-ai/langflow/pull/71
- Release 0.0.46 by @ibiscp in https://github.com/logspace-ai/langflow/pull/77
- Release 0.0.46 by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/78

**Full Changelog**: https://github.com/logspace-ai/langflow/compare/v0.0.45...v0.0.46

## v0.0.45

### What's Changed

- fix: deactivate replace_port by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/56
- Release 0.0.45 by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/57

**Full Changelog**: https://github.com/logspace-ai/langflow/compare/v0.0.44...v0.0.45

## v0.0.44

### What's Changed

- feat: added star history to README by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/44
- fix: new frontend dev.dockerfile by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/48
- fix: new frontend dev.dockerfile by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/52
- Fix: Dynamic tooltipTitle, id mapping bugfix for last ParameterCompon… by @ScripterSugar in https://github.com/logspace-ai/langflow/pull/51
- Add gpt4 by @ibiscp in https://github.com/logspace-ai/langflow/pull/55
- Release by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/49

#### New Contributors

- @ScripterSugar made their first contribution in https://github.com/logspace-ai/langflow/pull/51

**Full Changelog**: https://github.com/logspace-ai/langflow/compare/v0.0.40...v0.0.44

## v0.0.40

### What's Changed

- Replace langchain by @ibiscp in https://github.com/logspace-ai/langflow/pull/31
- Windows now uses Uvicorn by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/33
- Fix docker examples by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/34
- refac: langflow_backend -> langflow by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/35
- refac: remove frontend folder from backend by @ibiscp in https://github.com/logspace-ai/langflow/pull/36
- version with dinamic port by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/37
- Release 0.0.40 by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/43

#### New Contributors

- @ibiscp made their first contribution in https://github.com/logspace-ai/langflow/pull/31

**Full Changelog**: https://github.com/logspace-ai/langflow/compare/v0.0.33...v0.0.40

## v0.0.33

### What's Changed

- Release 0.0.33 by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/24

**Full Changelog**: https://github.com/logspace-ai/langflow/compare/v0.0.32...v0.0.33

## v0.0.32

### What's Changed

- Release 0.0.32 by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/22

**Full Changelog**: https://github.com/logspace-ai/langflow/compare/v0.0.31...v0.0.32

## v0.0.31

### What's Changed

- MemoryCustom node added by @anovazzi1 in https://github.com/logspace-ai/langflow/pull/1
- Create CODE_OF_CONDUCT.md by @CarlosRodrigoCoelho in https://github.com/logspace-ai/langflow/pull/7
- feat: adding release and lint github actions by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/9
- Use uvicorn on macOS to avoid making the user set env variable by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/10
- Release 0.0.28 by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/11
- Update release.yml by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/12
- Release 0.0.29 by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/13
- Release 0.0.30 by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/14
- Release 0.0.30 by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/15
- Release 0.0.31 by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/16

#### New Contributors

- @anovazzi1 made their first contribution in https://github.com/logspace-ai/langflow/pull/1
- @CarlosRodrigoCoelho made their first contribution in https://github.com/logspace-ai/langflow/pull/7
- @ogabrielluiz made their first contribution in https://github.com/logspace-ai/langflow/pull/9

**Full Changelog**: https://github.com/logspace-ai/langflow/commits/v0.0.31
