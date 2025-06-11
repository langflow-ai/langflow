// src/constants/constants.ts

import custom from "../customization/config-constants";
import { languageMap } from "../types/components";

/**
 * invalid characters for flow name
 * @constant
 */
export const INVALID_CHARACTERS = [
  " ",
  ",",
  ".",
  ":",
  ";",
  "!",
  "?",
  "/",
  "\\",
  "(",
  ")",
  "[",
  "]",
  "\n",
];

/**
 * regex to highlight the variables in the text
 * @constant regexHighlight
 * @type {RegExp}
 * @default
 * @example
 * {{variable}} or {variable}
 * @returns {RegExp}
 * @description
 * This regex is used to highlight the variables in the text.
 * It matches the variables in the text that are between {{}} or {}.
 */

export const regexHighlight = /\{\{(.*?)\}\}|\{([^{}]+)\}/g;
export const specialCharsRegex = /[!@#$%^&*()\-_=+[\]{}|;:'",.<>/?\\`´]/;

export const programmingLanguages: languageMap = {
  javascript: ".js",
  python: ".py",
  java: ".java",
  c: ".c",
  cpp: ".cpp",
  "c++": ".cpp",
  "c#": ".cs",
  ruby: ".rb",
  php: ".php",
  swift: ".swift",
  "objective-c": ".m",
  kotlin: ".kt",
  typescript: ".ts",
  go: ".go",
  perl: ".pl",
  rust: ".rs",
  scala: ".scala",
  haskell: ".hs",
  lua: ".lua",
  shell: ".sh",
  sql: ".sql",
  html: ".html",
  css: ".css",
  // add more file extensions here, make sure the key is same as language prop in CodeBlock.tsx component
};
/**
 * Number maximum of components to scroll on tooltips
 * @constant
 */
export const MAX_LENGTH_TO_SCROLL_TOOLTIP = 200;

export const MESSAGES_TABLE_ORDER = [
  "timestamp",
  "message",
  "text",
  "sender",
  "sender_name",
  "session_id",
  "files",
];

/**
 * Number maximum of components to scroll on tooltips
 * @constant
 */
export const MAX_WORDS_HIGHLIGHT = 79;

/**
 * Limit of items before show scroll on fields modal
 * @constant
 */
export const limitScrollFieldsModal = 10;

/**
 * The base text for subtitle of Export Dialog (Toolbar)
 * @constant
 */
export const EXPORT_DIALOG_SUBTITLE = "Export flow as JSON file.";
/**
 * The base text for subtitle of Flow Settings (Menubar)
 * @constant
 */
export const SETTINGS_DIALOG_SUBTITLE =
  "Customize your flow details and settings.";

/**
 * The base text for subtitle of Flow Logs (Menubar)
 * @constant
 */
export const LOGS_DIALOG_SUBTITLE =
  "Explore detailed logs of events and transactions between components.";

/**
 * The base text for subtitle of Code Dialog (Toolbar)
 * @constant
 */
export const CODE_DIALOG_SUBTITLE =
  "Export your flow to integrate it using this code.";

/**
 * The base text for subtitle of Chat Form
 * @constant
 */
export const CHAT_FORM_DIALOG_SUBTITLE =
  "Interact with your AI. Monitor inputs, outputs and memories.";

/**
 * The base text for subtitle of Edit Node Dialog
 * @constant
 */
export const EDIT_DIALOG_SUBTITLE =
  "Adjust component's settings and define parameter visibility. Remember to save your changes.";

/**
 * The base text for subtitle of Code Dialog
 * @constant
 */
export const CODE_PROMPT_DIALOG_SUBTITLE =
  "Edit your Python code snippet. Refer to the Langflow documentation for more information on how to write your own component.";

export const CODE_DICT_DIALOG_SUBTITLE =
  "Customize your dictionary, adding or editing key-value pairs as needed. Supports adding new objects {} or arrays [].";

/**
 * The base text for subtitle of Prompt Dialog
 * @constant
 */
export const PROMPT_DIALOG_SUBTITLE =
  "Create your prompt. Prompts can help guide the behavior of a Language Model. Use curly brackets {} to introduce variables.";

export const CHAT_CANNOT_OPEN_TITLE = "Chat Cannot Open";

export const CHAT_CANNOT_OPEN_DESCRIPTION = "This is not a chat flow.";

export const FLOW_NOT_BUILT_TITLE = "Flow not built";

export const FLOW_NOT_BUILT_DESCRIPTION =
  "Please build the flow before chatting.";

/**
 * The base text for subtitle of Text Dialog
 * @constant
 */
export const TEXT_DIALOG_TITLE = "Edit text content";

/**
 * The base text for subtitle of Import Dialog
 * @constant
 */
export const IMPORT_DIALOG_SUBTITLE =
  "Import flows from a JSON file or choose from pre-existing examples.";

/**
 * The text that shows when a tooltip is empty
 * @constant
 */
export const TOOLTIP_EMPTY = "No compatible components found.";

export const CSVViewErrorTitle = "CSV output";

export const CSVNoDataError = "No data available";

export const PDFViewConstant = "Expand the ouptut to see the PDF";

export const CSVError = "Error loading CSV";

export const PDFLoadErrorTitle = "Error loading PDF";

export const PDFCheckFlow = "Please check your flow and try again";

export const PDFErrorTitle = "PDF Output";

export const PDFLoadError = "Run the flow to see the pdf";

export const IMGViewConstant = "Expand the view to see the image";

export const IMGViewErrorMSG =
  "Run the flow or inform a valid url to see your image";

export const IMGViewErrorTitle = "Image output";

/**
 * The base text for subtitle of code dialog
 * @constant
 */
export const EXPORT_CODE_DIALOG =
  "Generate the code to integrate your flow into an external application.";

/**
 * The base text for subtitle of code dialog
 * @constant
 */
export const COLUMN_DIV_STYLE =
  " w-full h-full flex overflow-auto flex-col bg-muted px-16 ";

export const NAV_DISPLAY_STYLE =
  " w-full flex justify-between py-12 pb-2 px-6 ";

/**
 * The base text for subtitle of code dialog
 * @constant
 */
export const DESCRIPTIONS: string[] = [
  "Chain the Words, Master Language!",
  "Language Architect at Work!",
  "Empowering Language Engineering.",
  "Craft Language Connections Here.",
  "Create, Connect, Converse.",
  "Smart Chains, Smarter Conversations.",
  "Bridging Prompts for Brilliance.",
  "Language Models, Unleashed.",
  "Your Hub for Text Generation.",
  "Promptly Ingenious!",
  "Building Linguistic Labyrinths.",
  "Langflow: Create, Chain, Communicate.",
  "Connect the Dots, Craft Language.",
  "Interactive Language Weaving.",
  "Generate, Innovate, Communicate.",
  "Conversation Catalyst Engine.",
  "Language Chainlink Master.",
  "Design Dialogues with Langflow.",
  "Nurture NLP Nodes Here.",
  "Conversational Cartography Unlocked.",
  "Design, Develop, Dialogize.",
];
export const BUTTON_DIV_STYLE =
  " flex gap-2 focus:ring-1 focus:ring-offset-1 focus:ring-ring focus:outline-none ";

/**
 * The base text for subtitle of code dialog
 * @constant
 */
export const ADJECTIVES: string[] = [
  "admiring",
  "adoring",
  "agitated",
  "amazing",
  "angry",
  "awesome",
  "backstabbing",
  "berserk",
  "big",
  "boring",
  "clever",
  "cocky",
  "compassionate",
  "condescending",
  "cranky",
  "desperate",
  "determined",
  "distracted",
  "dreamy",
  "drunk",
  "ecstatic",
  "elated",
  "elegant",
  "evil",
  "fervent",
  "focused",
  "furious",
  "gigantic",
  "gloomy",
  "goofy",
  "grave",
  "happy",
  "high",
  "hopeful",
  "hungry",
  "insane",
  "jolly",
  "jovial",
  "kickass",
  "lonely",
  "loving",
  "mad",
  "modest",
  "naughty",
  "nauseous",
  "nostalgic",
  "pedantic",
  "pensive",
  "prickly",
  "reverent",
  "romantic",
  "sad",
  "serene",
  "sharp",
  "sick",
  "silly",
  "sleepy",
  "small",
  "stoic",
  "stupefied",
  "suspicious",
  "tender",
  "thirsty",
  "tiny",
  "trusting",
  "bubbly",
  "charming",
  "cheerful",
  "comical",
  "dazzling",
  "delighted",
  "dynamic",
  "effervescent",
  "enthusiastic",
  "exuberant",
  "fluffy",
  "friendly",
  "funky",
  "giddy",
  "giggly",
  "gleeful",
  "goofy",
  "graceful",
  "grinning",
  "hilarious",
  "inquisitive",
  "joyous",
  "jubilant",
  "lively",
  "mirthful",
  "mischievous",
  "optimistic",
  "peppy",
  "perky",
  "playful",
  "quirky",
  "radiant",
  "sassy",
  "silly",
  "spirited",
  "sprightly",
  "twinkly",
  "upbeat",
  "vibrant",
  "witty",
  "zany",
  "zealous",
];
/**
 * Nouns for the name of the flow
 * @constant
 *
 */
export const NOUNS: string[] = [
  "albattani",
  "allen",
  "almeida",
  "archimedes",
  "ardinghelli",
  "aryabhata",
  "austin",
  "babbage",
  "banach",
  "bardeen",
  "bartik",
  "bassi",
  "bell",
  "bhabha",
  "bhaskara",
  "blackwell",
  "bohr",
  "booth",
  "borg",
  "bose",
  "boyd",
  "brahmagupta",
  "brattain",
  "brown",
  "carson",
  "chandrasekhar",
  "colden",
  "cori",
  "cray",
  "curie",
  "darwin",
  "davinci",
  "dijkstra",
  "dubinsky",
  "easley",
  "einstein",
  "elion",
  "engelbart",
  "euclid",
  "euler",
  "fermat",
  "fermi",
  "feynman",
  "franklin",
  "galileo",
  "gates",
  "goldberg",
  "goldstine",
  "goldwasser",
  "golick",
  "goodall",
  "hamilton",
  "hawking",
  "heisenberg",
  "heyrovsky",
  "hodgkin",
  "hoover",
  "hopper",
  "hugle",
  "hypatia",
  "jang",
  "jennings",
  "jepsen",
  "joliot",
  "jones",
  "kalam",
  "kare",
  "keller",
  "khorana",
  "kilby",
  "kirch",
  "knuth",
  "kowalevski",
  "lalande",
  "lamarr",
  "leakey",
  "leavitt",
  "lichterman",
  "liskov",
  "lovelace",
  "lumiere",
  "mahavira",
  "mayer",
  "mccarthy",
  "mcclintock",
  "mclean",
  "mcnulty",
  "meitner",
  "meninsky",
  "mestorf",
  "minsky",
  "mirzakhani",
  "morse",
  "murdock",
  "newton",
  "nobel",
  "noether",
  "northcutt",
  "noyce",
  "panini",
  "pare",
  "pasteur",
  "payne",
  "perlman",
  "pike",
  "poincare",
  "poitras",
  "ptolemy",
  "raman",
  "ramanujan",
  "ride",
  "ritchie",
  "roentgen",
  "rosalind",
  "saha",
  "sammet",
  "shaw",
  "shirley",
  "shockley",
  "sinoussi",
  "snyder",
  "spence",
  "stallman",
  "stonebraker",
  "swanson",
  "swartz",
  "swirles",
  "tesla",
  "thompson",
  "torvalds",
  "turing",
  "varahamihira",
  "visvesvaraya",
  "volhard",
  "wescoff",
  "williams",
  "wilson",
  "wing",
  "wozniak",
  "wright",
  "yalow",
  "yonath",
  "coulomb",
  "degrasse",
  "dewey",
  "edison",
  "eratosthenes",
  "faraday",
  "galton",
  "gauss",
  "herschel",
  "hubble",
  "joule",
  "kaku",
  "kepler",
  "khayyam",
  "lavoisier",
  "maxwell",
  "mendel",
  "mendeleev",
  "ohm",
  "pascal",
  "planck",
  "riemann",
  "schrodinger",
  "sagan",
  "tesla",
  "tyson",
  "volta",
  "watt",
  "weber",
  "wien",
  "zoBell",
  "zuse",
];

/**
 * Header text for user projects
 * @constant
 *
 */
export const USER_PROJECTS_HEADER = "My Collection";

export const DEFAULT_FOLDER = "Starter Project";
export const DEFAULT_FOLDER_DEPRECATED = "My Projects";

/**
 * Header text for admin page
 * @constant
 *
 */
export const ADMIN_HEADER_TITLE = "Admin Page";

/**
 * Header description for admin page
 * @constant
 *
 */
export const ADMIN_HEADER_DESCRIPTION =
  "Navigate through this section to efficiently oversee all application users. From here, you can seamlessly manage user accounts.";

export const BASE_URL_API = custom.BASE_URL_API || "/api/v1/";

export const BASE_URL_API_V2 = custom.BASE_URL_API_V2 || "/api/v2/";

/**
 * URLs excluded from error retries.
 * @constant
 *
 */
export const URL_EXCLUDED_FROM_ERROR_RETRIES = [
  `${BASE_URL_API}validate/code`,
  `${BASE_URL_API}custom_component`,
  `${BASE_URL_API}validate/prompt`,
  `${BASE_URL_API}/login`,
  `${BASE_URL_API}api_key/store`,
];

export const skipNodeUpdate = [
  "CustomComponent",
  "PromptTemplate",
  "ChatMessagePromptTemplate",
  "SystemMessagePromptTemplate",
  "HumanMessagePromptTemplate",
];

export const CONTROL_INPUT_STATE = {
  password: "",
  cnfPassword: "",
  username: "",
};

export const CONTROL_PATCH_USER_STATE = {
  password: "",
  cnfPassword: "",
  profilePicture: "",
  apikey: "",
};

export const CONTROL_LOGIN_STATE = {
  username: "",
  password: "",
};

export const CONTROL_NEW_USER = {
  username: "",
  password: "",
  is_active: false,
  is_superuser: false,
};

export const tabsCode = [];

export const FETCH_ERROR_MESSAGE = "Couldn't establish a connection.";
export const FETCH_ERROR_DESCRIPION =
  "Check if everything is working properly and try again.";

export const TIMEOUT_ERROR_MESSAGE =
  "Please wait a few moments while the server processes your request.";
export const TIMEOUT_ERROR_DESCRIPION = "Server is busy.";

export const SIGN_UP_SUCCESS = "Account created! Await admin activation. ";

export const API_PAGE_PARAGRAPH =
  "Your secret Langflow API keys are listed below. Do not share your API key with others, or expose it in the browser or other client-side code.";

export const API_PAGE_USER_KEYS =
  "This user does not have any keys assigned at the moment.";

export const LAST_USED_SPAN_1 = "The last time this key was used.";

export const LAST_USED_SPAN_2 =
  "Accurate to within the hour from the most recent usage.";

export const LANGFLOW_SUPPORTED_TYPES = new Set([
  "str",
  "bool",
  "float",
  "code",
  "prompt",
  "file",
  "int",
  "dict",
  "NestedDict",
  "table",
  "link",
  "slider",
  "tab",
  "sortableList",
  "connect",
  "auth",
  "query",
  "mcp",
  "tools",
]);

export const FLEX_VIEW_TYPES = ["bool"];

export const priorityFields = new Set(["code", "template", "mode"]);

export const INPUT_TYPES = new Set([
  "ChatInput",
  // "TextInput",
  // "KeyPairInput",
  // "JsonInput",
  // "StringListInput",
]);
export const OUTPUT_TYPES = new Set([
  "ChatOutput",
  // "TextOutput",
  // "PDFOutput",
  // "ImageOutput",
  // "CSVOutput",
  // "JsonOutput",
  // "KeyPairOutput",
  // "StringListOutput",
  // "DataOutput",
  // "TableOutput",
]);

export const CHAT_FIRST_INITIAL_TEXT =
  "Start a conversation and click the agent's memories";

export const TOOLTIP_OUTDATED_NODE =
  "Your component is outdated. Click to update (data may be lost)";

export const CHAT_SECOND_INITIAL_TEXT = "to inspect previous messages.";

export const TOOLTIP_OPEN_HIDDEN_OUTPUTS = "Expand hidden outputs";
export const TOOLTIP_HIDDEN_OUTPUTS = "Collapse hidden outputs";

export const ZERO_NOTIFICATIONS = "No new notifications";

export const SUCCESS_BUILD = "Built sucessfully ✨";

export const ALERT_SAVE_WITH_API =
  "Caution: Unchecking this box only removes API keys from fields specifically designated for API keys.";

export const SAVE_WITH_API_CHECKBOX = "Save with my API keys";
export const EDIT_TEXT_MODAL_TITLE = "Edit Text";
export const EDIT_TEXT_PLACEHOLDER = "Type message here.";
export const INPUT_HANDLER_HOVER = "Avaliable input components:";
export const OUTPUT_HANDLER_HOVER = "Avaliable output components:";
export const TEXT_INPUT_MODAL_TITLE = "Inputs";
export const OUTPUTS_MODAL_TITLE = "Outputs";
export const LANGFLOW_CHAT_TITLE = "Langflow Chat";
export const CHAT_INPUT_PLACEHOLDER =
  "No chat input variables found. Click to run your flow.";
export const CHAT_INPUT_PLACEHOLDER_SEND = "Send a message...";
export const EDIT_CODE_TITLE = "Edit Code";
export const MY_COLLECTION_DESC =
  "Manage your projects. Download and upload entire collections.";
export const STORE_DESC = "Explore community-shared flows and components.";
export const STORE_TITLE = "Langflow Store";
export const NO_API_KEY = "You don't have an API key.";
export const INSERT_API_KEY = "Insert your Langflow API key.";
export const INVALID_API_KEY = "Your API key is not valid. ";
export const CREATE_API_KEY = `Don't have an API key? Sign up at`;
export const STATUS_BUILD = "Build to validate status.";
export const STATUS_INACTIVE = "Execution blocked";
export const STATUS_BUILDING = "Building...";
export const SAVED_HOVER = "Last saved: ";
export const RUN_TIMESTAMP_PREFIX = "Last Run: ";
export const STARTER_FOLDER_NAME = "Starter Projects";
export const PRIORITY_SIDEBAR_ORDER = [
  "saved_components",
  "inputs",
  "outputs",
  "prompts",
  "data",
  "prompt",
  "models",
  "helpers",
  "vectorstores",
  "embeddings",
];

export const BUNDLES_SIDEBAR_FOLDER_NAMES = [
  "notion",
  "Notion",
  "AssemblyAI",
  "assemblyai",
  "LangWatch",
  "langwatch",
  "Youtube",
  "youtube",
];

export const AUTHORIZED_DUPLICATE_REQUESTS = [
  "/health",
  "/flows",
  "/logout",
  "/refresh",
  "/login",
  "/auto_login",
];

export const BROKEN_EDGES_WARNING =
  "Some connections were removed because they were invalid:";

export const SAVE_DEBOUNCE_TIME = 300;

export const IS_MAC =
  typeof navigator !== "undefined" &&
  navigator.userAgent.toUpperCase().includes("MAC");

export const defaultShortcuts = [
  {
    display_name: "Controls",
    name: "Advanced Settings",
    shortcut: "mod+shift+a",
  },
  {
    display_name: "Search Components on Sidebar",
    name: "Search Components Sidebar",
    shortcut: "/",
  },
  {
    display_name: "Minimize",
    name: "Minimize",
    shortcut: "mod+.",
  },
  {
    display_name: "Code",
    name: "Code",
    shortcut: "space",
  },
  {
    display_name: "Copy",
    name: "Copy",
    shortcut: "mod+c",
  },
  {
    display_name: "Duplicate",
    name: "Duplicate",
    shortcut: "mod+d",
  },
  {
    display_name: "Component Share",
    name: "Component Share",
    shortcut: "mod+shift+s",
  },
  {
    display_name: "Docs",
    name: "Docs",
    shortcut: "mod+shift+d",
  },
  {
    display_name: "Changes Save",
    name: "Changes Save",
    shortcut: "mod+s",
  },
  {
    display_name: "Save Component",
    name: "Save Component",
    shortcut: "mod+alt+s",
  },
  {
    display_name: "Delete",
    name: "Delete",
    shortcut: "backspace",
  },
  {
    display_name: "Open Playground",
    name: "Open Playground",
    shortcut: "mod+k",
  },
  {
    display_name: "Undo",
    name: "Undo",
    shortcut: "mod+z",
  },
  {
    display_name: "Redo",
    name: "Redo",
    shortcut: "mod+y",
  },
  {
    display_name: "Redo (alternative)",
    name: "Redo Alt",
    shortcut: "mod+shift+z",
  },
  {
    display_name: "Group",
    name: "Group",
    shortcut: "mod+g",
  },
  {
    display_name: "Cut",
    name: "Cut",
    shortcut: "mod+x",
  },
  {
    display_name: "Paste",
    name: "Paste",
    shortcut: "mod+v",
  },
  {
    display_name: "API",
    name: "API",
    shortcut: "r",
  },
  {
    display_name: "Download",
    name: "Download",
    shortcut: "mod+j",
  },
  {
    display_name: "Update",
    name: "Update",
    shortcut: "mod+u",
  },
  {
    display_name: "Freeze",
    name: "Freeze Path",
    shortcut: "mod+shift+f",
  },
  {
    display_name: "Flow Share",
    name: "Flow Share",
    shortcut: "mod+shift+b",
  },
  {
    display_name: "Play",
    name: "Play",
    shortcut: "p",
  },
  {
    display_name: "Output Inspection",
    name: "Output Inspection",
    shortcut: "o",
  },
  {
    display_name: "Tool Mode",
    name: "Tool Mode",
    shortcut: "mod+shift+m",
  },
  {
    display_name: "Toggle Sidebar",
    name: "Toggle Sidebar",
    shortcut: "mod+b",
  },
];

export const DEFAULT_TABLE_ALERT_MSG = `Oops! It seems there's no data to display right now. Please check back later.`;

export const DEFAULT_TABLE_ALERT_TITLE = "No Data Available";

export const NO_COLUMN_DEFINITION_ALERT_TITLE = "No Column Definitions";

export const NO_COLUMN_DEFINITION_ALERT_DESCRIPTION =
  "There are no column definitions available for this table.";

export const LOCATIONS_TO_RETURN = ["/flow/", "/settings/"];

export const MAX_BATCH_SIZE = 50;

export const MODAL_CLASSES =
  "nopan nodelete nodrag  noflow fixed inset-0 bottom-0 left-0 right-0 top-0 z-50 overflow-auto bg-black/50 backdrop-blur-sm data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0";

export const ALLOWED_IMAGE_INPUT_EXTENSIONS = ["png", "jpg", "jpeg"];

export const componentsToIgnoreUpdate = ["CustomComponent"];

export const FS_ERROR_TEXT =
  "Please ensure your file has one of the following extensions:";
export const SN_ERROR_TEXT = ALLOWED_IMAGE_INPUT_EXTENSIONS.join(", ");

export const ERROR_UPDATING_COMPONENT =
  "An unexpected error occurred while updating the Component. Please try again.";
export const TITLE_ERROR_UPDATING_COMPONENT =
  "Error while updating the Component";

export const EMPTY_INPUT_SEND_MESSAGE = "No input message provided.";

export const EMPTY_OUTPUT_SEND_MESSAGE = "Message empty.";

export const TABS_ORDER = [
  "curl",
  "python api",
  "js api",
  "python code",
  "chat widget html",
];

export const LANGFLOW_ACCESS_TOKEN = "access_token_lf";
export const LANGFLOW_API_TOKEN = "apikey_tkn_lflw";
export const LANGFLOW_AUTO_LOGIN_OPTION = "auto_login_lf";
export const LANGFLOW_REFRESH_TOKEN = "refresh_token_lf";

export const LANGFLOW_ACCESS_TOKEN_EXPIRE_SECONDS = 60 * 60 - 60 * 60 * 0.1;
export const LANGFLOW_ACCESS_TOKEN_EXPIRE_SECONDS_ENV =
  Number(process.env?.ACCESS_TOKEN_EXPIRE_SECONDS ?? 60) -
  Number(process.env?.ACCESS_TOKEN_EXPIRE_SECONDS ?? 60) * 0.1;
export const TEXT_FIELD_TYPES: string[] = ["str", "SecretStr"];
export const NODE_WIDTH = 384;
export const NODE_HEIGHT = NODE_WIDTH * 3;

export const SHORTCUT_KEYS = ["cmd", "ctrl", "mod", "alt", "shift"];

export const SERVER_HEALTH_INTERVAL = 10000;
export const REFETCH_SERVER_HEALTH_INTERVAL = 20000;
export const DRAG_EVENTS_CUSTOM_TYPESS = {
  genericnode: "genericNode",
  notenode: "noteNode",
  "text/plain": "text/plain",
};

export const NOTE_NODE_MIN_WIDTH = 324;
export const NOTE_NODE_MIN_HEIGHT = 324;
export const NOTE_NODE_MAX_HEIGHT = 800;
export const NOTE_NODE_MAX_WIDTH = 600;

export const COLOR_OPTIONS = {
  amber: "hsl(var(--note-amber))",
  neutral: "hsl(var(--note-neutral))",
  rose: "hsl(var(--note-rose))",
  blue: "hsl(var(--note-blue))",
  lime: "hsl(var(--note-lime))",
  transparent: null,
};

export const maxSizeFilesInBytes = 10 * 1024 * 1024; // 10MB in bytes
export const MAX_TEXT_LENGTH = 99999;

export const SEARCH_TABS = ["All", "Flows", "Components"];
export const PAGINATION_SIZE = 12;
export const PAGINATION_PAGE = 1;

export const STORE_PAGINATION_SIZE = 12;
export const STORE_PAGINATION_PAGE = 1;

export const PAGINATION_ROWS_COUNT = [12, 24, 48, 96];
export const STORE_PAGINATION_ROWS_COUNT = [12, 24, 48, 96];

export const GRADIENT_CLASS =
  "linear-gradient(to right, hsl(var(--background) / 0.3), hsl(var(--background)))";

export const GRADIENT_CLASS_DISABLED =
  "linear-gradient(to right, hsl(var(--muted) / 0.3), hsl(var(--muted)))";

export const RECEIVING_INPUT_VALUE = "Receiving input";
export const SELECT_AN_OPTION = "Select an option";

export const ICON_STROKE_WIDTH = 1.5;

export const DEFAULT_PLACEHOLDER = "Type something...";

export const DEFAULT_TOOLSET_PLACEHOLDER = "Used as a tool";

export const SAVE_API_KEY_ALERT = "API key saved successfully";
export const PLAYGROUND_BUTTON_NAME = "Playground";
export const POLLING_MESSAGES = {
  ENDPOINT_NOT_AVAILABLE: "Endpoint not available",
  STREAMING_NOT_SUPPORTED: "Streaming not supported",
} as const;

export const BUILD_POLLING_INTERVAL = 25;

export const IS_AUTO_LOGIN =
  !process?.env?.LANGFLOW_AUTO_LOGIN ||
  String(process?.env?.LANGFLOW_AUTO_LOGIN)?.toLowerCase() !== "false";

export const AUTO_LOGIN_RETRY_DELAY = 2000;
export const AUTO_LOGIN_MAX_RETRY_DELAY = 60000;

export const ALL_LANGUAGES = [
  { value: "en-US", name: "English (US)" },
  { value: "en-GB", name: "English (UK)" },
  { value: "it-IT", name: "Italian" },
  { value: "fr-FR", name: "French" },
  { value: "es-ES", name: "Spanish" },
  { value: "de-DE", name: "German" },
  { value: "ja-JP", name: "Japanese" },
  { value: "pt-BR", name: "Portuguese (Brazil)" },
  { value: "zh-CN", name: "Chinese (Simplified)" },
  { value: "ru-RU", name: "Russian" },
  { value: "ar-SA", name: "Arabic" },
  { value: "hi-IN", name: "Hindi" },
];

export const DEBOUNCE_FIELD_LIST = [
  "SecretStrInput",
  "MessageTextInput",
  "TextInput",
  "MultilineInput",
  "SecretStrInput",
  "IntInput",
  "FloatInput",
  "SliderInput",
];

export const OPENAI_VOICES = [
  { name: "alloy", value: "alloy" },
  { name: "ash", value: "ash" },
  { name: "ballad", value: "ballad" },
  { name: "coral", value: "coral" },
  { name: "echo", value: "echo" },
  { name: "sage", value: "sage" },
  { name: "shimmer", value: "shimmer" },
  { name: "verse", value: "verse" },
];

export const DEFAULT_POLLING_INTERVAL = 5000;
export const DEFAULT_TIMEOUT = 30000;
export const DEFAULT_FILE_PICKER_TIMEOUT = 60000;
export const DISCORD_URL = "https://discord.com/invite/EqksyE2EX9";
export const GITHUB_URL = "https://github.com/langflow-ai/langflow";
export const TWITTER_URL = "https://x.com/langflow_ai";
export const DOCS_URL = "https://docs.langflow.org";
export const DATASTAX_DOCS_URL =
  "https://docs.datastax.com/en/langflow/index.html";

export const UUID_PARSING_ERROR = "uuid_parsing";
