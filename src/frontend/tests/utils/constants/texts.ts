/**
 * Centralised UI text strings referenced from more than one spec file.
 *
 * Every string here was found in ≥ 5 spec files by the analysis script
 * in `CZL/E2E_TESTS_REFACTOR_PROPOSAL.md`. Specs that touch only one of
 * these strings should still use the constant — a single rename in the
 * product UI then needs only one change here.
 *
 * Scope: text the production UI renders (labels, placeholders, toast
 * messages, role names) and the fill values that have to match it. Do
 * NOT add per-test fixture strings ("my first session", "Say hi",
 * "edit_bot_1") — those are scenario data, not UI invariants.
 */
export const TEXTS = {
  // ─── Action buttons / menu items ────────────────────────────────────
  /** Generic "Close" button — modals, popovers, fullscreen exits. */
  close: "Close",
  /** Generic "Delete" button — confirmation modals, sidebar menus. */
  delete: "Delete",
  /** Generic "Save" button — settings, profile, etc. */
  save: "Save",
  /** "Check & Save" submit on custom-component code editor. */
  checkAndSave: "Check & Save",
  /** "Edit Prompt" trigger on Prompt template node. */
  editPrompt: "Edit Prompt",
  /** Sign-in form submit button (role=button, name="Sign In"). */
  signIn: "Sign In",
  /** Build-cancel button (role=button, name="Stop"). */
  stop: "Stop",
  /** App header / user menu items. */
  settings: "Settings",
  logout: "Logout",
  exit: "Exit",
  /** Right-hand panel toggle (role=button, name="Playground"). */
  playground: "Playground",

  // ─── Starter projects / templates (heading or card names) ───────────
  templateBasicPrompting: "Basic Prompting",
  templateSimpleAgent: "Simple Agent",
  templateBasicRag: "Basic RAG",

  // ─── Component display names (sidebar & canvas labels) ──────────────
  componentChatInput: "Chat Input",
  componentLanguageModel: "Language Model",
  componentOutput: "Component Output",

  // ─── Generic UI labels rendered in the projects/main page ───────────
  labelNewProject: "New Project",
  labelMyFiles: "My Files",
  labelComponents: "Components",
  /** Sub-section of the agent panel — rendered both as plain text and as
   *  the `text=toolset` waitForSelector target. */
  labelToolset: "toolset",
  labelNoInputMessage: "No input message provided.",
  labelHelloFromAi: "Hello from AI",

  // ─── Toasts / status messages ───────────────────────────────────────
  toastProjectDeleted: "Project deleted successfully",
  toastApiKeySaved: "Success! Your API Key has been saved.", // pragma: allowlist secret
  /** Sub-string emitted by the build-flow log when a build finishes
   *  successfully — used as `text=built successfully` in 36 specs. */
  toastBuiltSuccessfully: "built successfully",

  // ─── Auth / login screen ────────────────────────────────────────────
  /** Visible on the sign-in route when LANGFLOW_AUTO_LOGIN=false. */
  authSignInHeader: "sign in to langflow",
  /** Default seeded username. */
  authDefaultCredential: "langflow",
  /** Explicit Playwright-only superuser password seeded in playwright.config.ts. */
  authDefaultPassword: "test-superuser-password", // pragma: allowlist secret

  // ─── Form placeholders (getByPlaceholder) ───────────────────────────
  placeholderUsername: "Username",
  placeholderPassword: "Password", // pragma: allowlist secret
  placeholderMessage: "Message",
  placeholderEmpty: "Empty",
  placeholderApiKey: "Insert your API Key", // pragma: allowlist secret
  placeholderSendMessage: "Send a message...",
  placeholderVariableName: "Enter a name for the variable...",

  // ─── Sidebar search queries (.fill(...) on the components search) ───
  /** NOTE: these are the LOWERCASE strings typed into the sidebar
   *  search input — separate from the display-name constants above
   *  (`componentChatInput`, etc.) which are PascalCase / Title Case. */
  searchChatInput: "chat input",
  searchChatOutput: "chat output",
  searchTextInput: "text input",
  searchTextOutput: "text output",
  searchPrompt: "prompt",
  searchUrl: "url",
  /** Provider names — uppercase as rendered in the model-provider modal. */
  providerOpenAi: "OpenAI",
  /** Same provider as a lowercase search query. */
  providerOpenAiSearch: "openai",
} as const;
