// src/constants/constants.ts

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
export const SETTINGS_DIALOG_SUBTITLE = "Edit details about your project.";

/**
 * The base text for subtitle of Flow Logs (Menubar)
 * @constant
 */
export const LOGS_DIALOG_SUBTITLE = "Check out information about your flow.";

/**
 * The base text for subtitle of Code Dialog (Toolbar)
 * @constant
 */
export const CODE_DIALOG_SUBTITLE =
  "Export your flow to use it with this code.";

/**
 * The base text for subtitle of Chat Form
 * @constant
 */
export const CHAT_FORM_DIALOG_SUBTITLE =
  "Set up the input variables defined in prompt templates. Interact with agents and chains.";

/**
 * The base text for subtitle of Edit Node Dialog
 * @constant
 */
export const EDIT_DIALOG_SUBTITLE =
  "Adjust the configurations of your component. Define parameter visibility for the canvas view. Remember to save once you’re finished.";

/**
 * The base text for subtitle of Code Dialog
 * @constant
 */
export const CODE_PROMPT_DIALOG_SUBTITLE =
  "Edit your Python code. This code snippet accepts module import and a single function definition. Make sure that your function returns a string.";

export const CODE_DICT_DIALOG_SUBTITLE =
  "Edit your dictionary. This dialog allows you to create your own customized dictionary. You can add as many key-value pairs as you want. While in edit mode, you can enter ({}) or ([]), and this will result in adding a new object or array.";
/**
 * The base text for subtitle of Prompt Dialog
 * @constant
 */
export const PROMPT_DIALOG_SUBTITLE =
  "Create your prompt. Prompts can help guide the behavior of a Language Model.";

export const CHAT_CANNOT_OPEN_TITLE = "Chat Cannot Open";

export const CHAT_CANNOT_OPEN_DESCRIPTION = "This is not a chat flow.";

export const FLOW_NOT_BUILT_TITLE = "Flow not built";

export const FLOW_NOT_BUILT_DESCRIPTION =
  "Please build the flow before chatting.";

/**
 * The base text for subtitle of Text Dialog
 * @constant
 */
export const TEXT_DIALOG_SUBTITLE = "Edit your text.";

/**
 * The base text for subtitle of Import Dialog
 * @constant
 */
export const IMPORT_DIALOG_SUBTITLE =
  "Upload a JSON file or select from the available community examples.";

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

export const DEFAULT_FOLDER = "My Projects";

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

export const BASE_URL_API = "/api/v1/";

export const BACKEND_URL = "http://localhost:7860/";

/**
 * URLs excluded from error retries.
 * @constant
 *
 */
export const URL_EXCLUDED_FROM_ERROR_RETRIES = [
  `${BASE_URL_API}validate/code`,
  `${BASE_URL_API}custom_component`,
  `${BASE_URL_API}validate/prompt`,
  `http://localhost:7860/login`,
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

export const SIGN_UP_SUCCESS = "Account created! Await admin activation. ";

export const API_PAGE_PARAGRAPH =
  "Your secret API keys are listed below. Do not share your API key with others, or expose it in the browser or other client-side code.";

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
]);

export const priorityFields = new Set(["code", "template"]);

export const INPUT_TYPES = new Set([
  "ChatInput",
  "TextInput",
  "KeyPairInput",
  "JsonInput",
  "StringListInput",
]);
export const OUTPUT_TYPES = new Set([
  "ChatOutput",
  "TextOutput",
  "PDFOutput",
  "ImageOutput",
  "CSVOutput",
  "JsonOutput",
  "KeyPairOutput",
  "StringListOutput",
  "RecordsOutput",
  "TableOutput",
]);

export const CHAT_FIRST_INITIAL_TEXT =
  "Start a conversation and click the agent's thoughts";

export const TOOLTIP_OUTDATED_NODE =
  "Your component is outdated. Click to update (data may be lost)";

export const CHAT_SECOND_INITIAL_TEXT = "to inspect the chaining process.";

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
  "Manage your personal projects. Download and upload entire collections.";
export const STORE_DESC = "Explore community-shared flows and components.";
export const STORE_TITLE = "Langflow Store";
export const NO_API_KEY = "You don't have an API key. ";
export const INSERT_API_KEY = "Insert your Langflow API key.";
export const INVALID_API_KEY = "Your API key is not valid. ";
export const CREATE_API_KEY = `Don’t have an API key? Sign up at`;
export const STATUS_BUILD = "Build to validate status.";
export const STATUS_BUILDING = "Building...";
export const SAVED_HOVER = "Last saved at ";
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
  "vectorsearch",
  "embeddings",
];
export const NATIVE_CATEGORIES = [
  "inputs",
  "outputs",
  "prompts",
  "data",
  "prompt",
  "models",
  "helpers",
  "experimental",
  "agents",
];

export const AUTHORIZED_DUPLICATE_REQUESTS = [
  "/health",
  "/flows",
  "/logout",
  "/refresh",
  "/login",
  "/auto_login",
];

export const SAVE_DEBOUNCE_TIME = 300;

export const IS_MAC = navigator.userAgent.toUpperCase().includes("MAC");

export const defaultShortcuts = [
  {
    name: "Advanced Settings",
    shortcut: `${IS_MAC ? "Cmd" : "Ctrl"} + Shift + A`,
  },
  {
    name: "Minimize",
    shortcut: `${IS_MAC ? "Cmd" : "Ctrl"} + Q`,
  },
  {
    name: "Code",
    shortcut: `Space`,
  },
  {
    name: "Copy",
    shortcut: `${IS_MAC ? "Cmd" : "Ctrl"} + C`,
  },
  {
    name: "Duplicate",
    shortcut: `${IS_MAC ? "Cmd" : "Ctrl"} + D`,
  },
  {
    name: "Component Share",
    shortcut: `${IS_MAC ? "Cmd" : "Ctrl"} + Shift + S`,
  },
  {
    name: "Docs",
    shortcut: `${IS_MAC ? "Cmd" : "Ctrl"} + Shift + D`,
  },
  {
    name: "Save",
    shortcut: `${IS_MAC ? "Cmd" : "Ctrl"} + S`,
  },
  {
    name: "Delete",
    shortcut: "Backspace",
  },
  {
    name: "Open playground",
    shortcut: `${IS_MAC ? "Cmd" : "Ctrl"} + K`,
  },
  {
    name: "Undo",
    shortcut: `${IS_MAC ? "Cmd" : "Ctrl"} + Z`,
  },
  {
    name: "Redo",
    shortcut: `${IS_MAC ? "Cmd" : "Ctrl"} + Y`,
  },
  {
    name: "Group",
    shortcut: `${IS_MAC ? "Cmd" : "Ctrl"} + G`,
  },
  {
    name: "Cut",
    shortcut: `${IS_MAC ? "Cmd" : "Ctrl"} + X`,
  },
  {
    name: "Paste",
    shortcut: `${IS_MAC ? "Cmd" : "Ctrl"} + V`,
  },
  {
    name: "API",
    shortcut: `R`,
  },
  {
    name: "Download",
    shortcut: `${IS_MAC ? "Cmd" : "Ctrl"} + J`,
  },
  {
    name: "Update",
    shortcut: `${IS_MAC ? "Cmd" : "Ctrl"} + U`,
  },
  {
    name: "Freeze",
    shortcut: `${IS_MAC ? "Cmd" : "Ctrl"} + F`,
  },
  {
    name: "Flow Share",
    shortcut: `${IS_MAC ? "Cmd" : "Ctrl"} + B`,
  },
  {
    name: "Play",
    shortcut: `P`,
  },
  {
    name: "Output Inspection",
    shortcut: `O`,
  },
];

export const DEFAULT_TABLE_ALERT_MSG = `Oops! It seems there's no data to display right now. Please check back later.`;

export const DEFAULT_TABLE_ALERT_TITLE = "No Data Available";

export const LOCATIONS_TO_RETURN = ["/flow/", "/settings/"];

export const MAX_BATCH_SIZE = 50;

export const MODAL_CLASSES =
  "nopan nodelete nodrag noundo nocopy fixed inset-0 bottom-0 left-0 right-0 top-0 z-50 overflow-auto bg-blur-shared backdrop-blur-sm data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0";
