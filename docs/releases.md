## v0.0.58

### What's Changed
* Fix bug when running LLM alone by @ibiscp in https://github.com/logspace-ai/langflow/pull/160
* Refactor tools by @ibiscp in https://github.com/logspace-ai/langflow/pull/176
* load_flow_from_json("path/to/flow.json") returns UnicodeDecodeError by @bigKeter in https://github.com/logspace-ai/langflow/pull/165
* Create a VM in a GCP project that serves the Langflow app by @genome21 in https://github.com/logspace-ai/langflow/pull/169
* Correct run instructions in Readme by @PaulLockett in https://github.com/logspace-ai/langflow/pull/87
* Add Import Examples Feature to Flow Editor by @anovazzi1 in https://github.com/logspace-ai/langflow/pull/175
* Change button placement by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/193
* API keys for LLMs and Embeddings are now loaded from env if available by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/195
* style(langflow): fix formatting and add type hinting to custom.py and run.py files by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/194
* Example loader and bugfixes by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/199

## New Contributors
* @bigKeter made their first contribution in https://github.com/logspace-ai/langflow/pull/165
* @genome21 made their first contribution in https://github.com/logspace-ai/langflow/pull/169
* @PaulLockett made their first contribution in https://github.com/logspace-ai/langflow/pull/87

## v0.0.57

### What's Changed
* Hotfix: psygopg2 might break installation by @ogabrielluiz in #168

## v0.0.56

### What's Changed
* Add contrib link to readme by @jacobhrussell in https://github.com/logspace-ai/langflow/pull/136
* Llama Support by @yoazmenda in https://github.com/logspace-ai/langflow/pull/134
* feat: added LLMFrontendNode by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/140
* Firefox password by @anovazzi1 in https://github.com/logspace-ai/langflow/pull/147
* removable edges implemented by @anovazzi1 in https://github.com/logspace-ai/langflow/pull/149
* Vector stores, embeddings, document loaders, and text splitters by @ibiscp in https://github.com/logspace-ai/langflow/pull/145
* Adding new fields to Chain nodes by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/148
* Add new docloaders and change the way files are loaded by @ibiscp in https://github.com/logspace-ai/langflow/pull/154
* Change docstring parser by @ibiscp in https://github.com/logspace-ai/langflow/pull/158
* Add SQL Agent by @ibiscp in https://github.com/logspace-ai/langflow/pull/159
* VectorStores, DocumentLoaders, TextSplitters, Embeddings and other additions by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/157

#### New Contributors
* @jacobhrussell made their first contribution in https://github.com/logspace-ai/langflow/pull/136
* @yoazmenda made their first contribution in https://github.com/logspace-ai/langflow/pull/134

**Full Changelog**: https://github.com/logspace-ai/langflow/compare/v0.0.55...v0.0.56

## v0.0.55

### What's Changed
* feat: chain template tests by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/125
* feat: adding prompt template tests by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/128
* feat: added agents tests by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/127
* refact: more maintable build_nodes by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/123
* Modifies frontend chatComponent to itemize validation errors by @cayal in https://github.com/logspace-ai/langflow/pull/126
* add minor fix for required fields that are not displayed by @anovazzi1 in https://github.com/logspace-ai/langflow/pull/129
* feat: added first tests for llms by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/130
* Update CONTRIBUTING.md by @jordi-adame in https://github.com/logspace-ai/langflow/pull/133
* Fixes to ChainCreator and PromptTemplate processing by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/135
* Fix tool bug by @ibiscp in https://github.com/logspace-ai/langflow/pull/137
* Fix bugs, add tests, and refactor code by @ibiscp in https://github.com/logspace-ai/langflow/pull/138

#### New Contributors
* @cayal made their first contribution in https://github.com/logspace-ai/langflow/pull/126
* @jordi-adame made their first contribution in https://github.com/logspace-ai/langflow/pull/133

**Full Changelog**: https://github.com/logspace-ai/langflow/compare/v0.0.54...v0.0.55

## v0.0.54

### What's Changed
* Remove tools until fixed by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/124
* Fix prompt validation exception condition by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/122


**Full Changelog**: https://github.com/logspace-ai/langflow/compare/v0.0.53...v0.0.54

## v0.0.53

### What's Changed
* Implementation of Agents as Tools and Custom Tools by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/79
* removed handle from code component by @anovazzi1 in https://github.com/logspace-ai/langflow/pull/83
* refac: Factory implementation of LangChainTypes by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/84
* Toolkits by @ibiscp in https://github.com/logspace-ai/langflow/pull/92
* Added initialize_agent and Memory by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/93
* fix: deactivate intermediate steps for now by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/97
* Chain loader by @ibiscp in https://github.com/logspace-ai/langflow/pull/98
* UI fixes by @anovazzi1 in https://github.com/logspace-ai/langflow/pull/99
* colorized think with ANSI to HTML by @anovazzi1 in https://github.com/logspace-ai/langflow/pull/101
* bug fixed when not implemented nodes are imported to the flow by @anovazzi1 in https://github.com/logspace-ai/langflow/pull/102
* delete the message that was sent when the backend returned an error by @anovazzi1 in https://github.com/logspace-ai/langflow/pull/105
* fixed validation error by @anovazzi1 in https://github.com/logspace-ai/langflow/pull/106
* Implement Memories, validation and other fixes by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/107
* fix: adding memory node and better exceptions by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/110
* UI improvements by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/112
* Bug fixes  by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/115
* Ui improvement by @anovazzi1 in https://github.com/logspace-ai/langflow/pull/114
* Prompt component by @anovazzi1 in https://github.com/logspace-ai/langflow/pull/116
* added colors to toolkits and wrappers by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/118


**Full Changelog**: https://github.com/logspace-ai/langflow/compare/v0.0.46...v0.0.53

## v0.0.52

### What's Changed
* fix: adding maintainers and other configs by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/59
* feat: added constants file to support model types and others by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/60
* UI updates by @anovazzi1 in https://github.com/logspace-ai/langflow/pull/63
* full dropdown clickable by @anovazzi1 in https://github.com/logspace-ai/langflow/pull/69
* Add config file with option to enable all features by @ibiscp in https://github.com/logspace-ai/langflow/pull/70
* UI updates by @anovazzi1 in https://github.com/logspace-ai/langflow/pull/71
* Release 0.0.46 by @ibiscp in https://github.com/logspace-ai/langflow/pull/77
* Release 0.0.46 by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/78


**Full Changelog**: https://github.com/logspace-ai/langflow/compare/v0.0.45...v0.0.52

## v0.0.46

### What's Changed
* fix: adding maintainers and other configs by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/59
* feat: added constants file to support model types and others by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/60
* UI updates by @anovazzi1 in https://github.com/logspace-ai/langflow/pull/63
* full dropdown clickable by @anovazzi1 in https://github.com/logspace-ai/langflow/pull/69
* Add config file with option to enable all features by @ibiscp in https://github.com/logspace-ai/langflow/pull/70
* UI updates by @anovazzi1 in https://github.com/logspace-ai/langflow/pull/71
* Release 0.0.46 by @ibiscp in https://github.com/logspace-ai/langflow/pull/77
* Release 0.0.46 by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/78


**Full Changelog**: https://github.com/logspace-ai/langflow/compare/v0.0.45...v0.0.46

## v0.0.45

### What's Changed
* fix: deactivate replace_port by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/56
* Release 0.0.45 by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/57


**Full Changelog**: https://github.com/logspace-ai/langflow/compare/v0.0.44...v0.0.45

## v0.0.44

### What's Changed
* feat: added star history to README by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/44
* fix: new frontend dev.dockerfile by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/48
* fix: new frontend dev.dockerfile by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/52
* Fix: Dynamic tooltipTitle, id mapping bugfix for last ParameterCompon… by @ScripterSugar in https://github.com/logspace-ai/langflow/pull/51
* Add gpt4 by @ibiscp in https://github.com/logspace-ai/langflow/pull/55
* Release by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/49

#### New Contributors
* @ScripterSugar made their first contribution in https://github.com/logspace-ai/langflow/pull/51

**Full Changelog**: https://github.com/logspace-ai/langflow/compare/v0.0.40...v0.0.44

## v0.0.40

### What's Changed
* Replace langchain by @ibiscp in https://github.com/logspace-ai/langflow/pull/31
* Windows now uses Uvicorn by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/33
* Fix docker examples by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/34
* refac: langflow_backend -> langflow by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/35
* refac: remove frontend folder from backend by @ibiscp in https://github.com/logspace-ai/langflow/pull/36
* version with dinamic port by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/37
* Release 0.0.40 by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/43

#### New Contributors
* @ibiscp made their first contribution in https://github.com/logspace-ai/langflow/pull/31

**Full Changelog**: https://github.com/logspace-ai/langflow/compare/v0.0.33...v0.0.40

## v0.0.33

### What's Changed
* Release 0.0.33 by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/24


**Full Changelog**: https://github.com/logspace-ai/langflow/compare/v0.0.32...v0.0.33

## v0.0.32

### What's Changed
* Release 0.0.32 by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/22


**Full Changelog**: https://github.com/logspace-ai/langflow/compare/v0.0.31...v0.0.32

## v0.0.31

### What's Changed
* MemoryCustom node added by @anovazzi1 in https://github.com/logspace-ai/langflow/pull/1
* Create CODE_OF_CONDUCT.md by @CarlosRodrigoCoelho in https://github.com/logspace-ai/langflow/pull/7
* feat: adding release and lint github actions by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/9
* Use uvicorn on macOS to avoid making the user set env variable by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/10
* Release 0.0.28 by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/11
* Update release.yml by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/12
* Release 0.0.29 by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/13
* Release 0.0.30 by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/14
* Release 0.0.30 by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/15
* Release 0.0.31 by @ogabrielluiz in https://github.com/logspace-ai/langflow/pull/16

#### New Contributors
* @anovazzi1 made their first contribution in https://github.com/logspace-ai/langflow/pull/1
* @CarlosRodrigoCoelho made their first contribution in https://github.com/logspace-ai/langflow/pull/7
* @ogabrielluiz made their first contribution in https://github.com/logspace-ai/langflow/pull/9

**Full Changelog**: https://github.com/logspace-ai/langflow/commits/v0.0.31