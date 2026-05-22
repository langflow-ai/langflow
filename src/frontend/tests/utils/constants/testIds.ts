/**
 * Centralised data-testid strings referenced from multiple spec files.
 *
 * Specs that touch only one of these test-ids should still use the
 * constant — a single rename in the UI then needs only one change here.
 */
export const TID = {
  // App shell
  mainpageTitle: "mainpage_title",
  newProjectBtn: "new-project-btn",
  newProjectBtnEmptyPage: "new_project_btn_empty_page",
  modalTitle: "modal-title",
  userProfileSettings: "user-profile-settings",

  // Flow editor
  blankFlow: "blank-flow",
  sidebarSearchInput: "sidebar-search-input",
  sidebarCustomComponentButton: "sidebar-custom-component-button",
  sideNavAllTemplates: "side_nav_options_all-templates",
  canvasControlsDropdown: "canvas_controls_dropdown",
  fitView: "fit_view",
  zoomOut: "zoom_out",
  divGenericNode: "div-generic-node",

  // Build / run
  buttonRunChatOutput: "button_run_chat output",
  buttonStop: "button-stop",
  playgroundBtnFlowIo: "playground-btn-flow-io",

  // Playground chat
  inputChatPlayground: "input-chat-playground",
  buttonSend: "button-send",
  chatMessage: "div-chat-message",
  sessionSelector: "session-selector",
  newChat: "new-chat",
  iconCoins: "icon-Coins",

  // Publish / shareable playground
  publishButton: "publish-button",
  publishSwitch: "publish-switch",
  shareablePlayground: "shareable-playground",
  apiAccessItem: "api-access-item",
  apiTabCurl: "api_tab_curl",

  // Settings
  settingsMenuHeader: "settings_menu_header",
  iconChevronLeft: "icon-ChevronLeft",

  // Model providers
  modelModel: "model_model",
  manageModelProviders: "manage-model-providers",
  popoverAnchorInputApiKey: "popover-anchor-input-api_key",

  // Edit / inspect
  editFieldsButton: "edit-fields-button",
  codeButtonModal: "code-button-modal",
} as const;

/**
 * Selector strings for elements without stable test-ids. Prefer adding a
 * test-id to the UI rather than expanding this list.
 */
export const SELECTORS = {
  reactFlowCanvasXPath: '//*[@id="react-flow-id"]',
  sessionMoreMenuPattern:
    '[data-testid^="session-"][data-testid$="-more-menu"]',
  providerItemPattern: '[data-testid^="provider-item-"]',
} as const;
