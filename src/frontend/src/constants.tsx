// src/constants.tsx

import { MessageSquare } from "lucide-react";
import { FlowType } from "./types/flow";
import { TabsState } from "./types/tabs";
import { buildInputs, buildTweaks } from "./utils";

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

/**
 * The base text for subtitle of Prompt Dialog
 * @constant
 */
export const PROMPT_DIALOG_SUBTITLE =
  "Create your prompt. Prompts can help guide the behavior of a Language Model.";

export const CHAT_CANNOT_OPEN_TITLE = "Chat Cannot Open";

export const CHAT_CANNOT_OPEN_DESCRIPTION = "This is not a chat flow.";

export const FLOW_NOT_BUILT_TITLE = "Flow not built";

export const THOUGHTS_ICON = MessageSquare;

export const FLOW_NOT_BUILT_DESCRIPTION =
  "Please build the flow before chatting.";

/**
 * The base text for subtitle of Text Dialog
 * @constant
 */
export const TEXT_DIALOG_SUBTITLE = "Edit your text.";

/**
 * Function to get the python code for the API
 * @param {string} flowId - The id of the flow
 * @returns {string} - The python code
 */
export const getPythonApiCode = (
  flow: FlowType,
  tweak?: any[],
  tabsState?: TabsState
): string => {
  const flowId = flow.id;

  // create a dictionary of node ids and the values is an empty dictionary
  // flow.data.nodes.forEach((node) => {
  //   node.data.id
  // }
  const tweaks = buildTweaks(flow);
  const inputs = buildInputs(tabsState, flow.id);
  return `import requests
from typing import Optional

BASE_API_URL = "${window.location.protocol}//${
    window.location.host
  }/api/v1/process"
FLOW_ID = "${flowId}"
# You can tweak the flow by adding a tweaks dictionary
# e.g {"OpenAI-XXXXX": {"model_name": "gpt-4"}}
TWEAKS = ${
    tweak && tweak.length > 0
      ? buildTweakObject(tweak)
      : JSON.stringify(tweaks, null, 2)
  }

def run_flow(inputs: dict, flow_id: str, tweaks: Optional[dict] = None) -> dict:
    """
    Run a flow with a given message and optional tweaks.

    :param message: The message to send to the flow
    :param flow_id: The ID of the flow to run
    :param tweaks: Optional tweaks to customize the flow
    :return: The JSON response from the flow
    """
    api_url = f"{BASE_API_URL}/{flow_id}"

    payload = {"inputs": inputs}

    if tweaks:
        payload["tweaks"] = tweaks

    response = requests.post(api_url, json=payload)
    return response.json()

# Setup any tweaks you want to apply to the flow
inputs = ${inputs}
print(run_flow(inputs, flow_id=FLOW_ID, tweaks=TWEAKS))`;
};
/**
 * Function to get the curl code for the API
 * @param {string} flowId - The id of the flow
 * @returns {string} - The curl code
 */
export const getCurlCode = (
  flow: FlowType,
  tweak?: any[],
  tabsState?: TabsState
): string => {
  const flowId = flow.id;
  const tweaks = buildTweaks(flow);
  const inputs = buildInputs(tabsState, flow.id);

  return `curl -X POST \\
  ${window.location.protocol}//${
    window.location.host
  }/api/v1/process/${flowId} \\
  -H 'Content-Type: application/json' \\
  -d '{"inputs": ${inputs}, "tweaks": ${
    tweak && tweak.length > 0
      ? buildTweakObject(tweak)
      : JSON.stringify(tweaks, null, 2)
  }}'`;
};
/**
 * Function to get the python code for the API
 * @param {string} flowName - The name of the flow
 * @returns {string} - The python code
 */
export const getPythonCode = (
  flow: FlowType,
  tweak?: any[],
  tabsState?: TabsState
): string => {
  const flowName = flow.name;
  const tweaks = buildTweaks(flow);
  const inputs = buildInputs(tabsState, flow.id);
  return `from langflow import load_flow_from_json
TWEAKS = ${
    tweak && tweak.length > 0
      ? buildTweakObject(tweak)
      : JSON.stringify(tweaks, null, 2)
  }
flow = load_flow_from_json("${flowName}.json", tweaks=TWEAKS)
# Now you can use it like any chain
inputs = ${inputs}
flow(inputs)`;
};

function buildTweakObject(tweak) {
  tweak.forEach((el) => {
    Object.keys(el).forEach((key) => {
      for (let kp in el[key]) {
        try {
          el[key][kp] = JSON.parse(el[key][kp]);
        } catch {}
      }
    });
  });

  const tweakString = JSON.stringify(tweak, null, 2);
  return tweakString;
}

/**
 * The base text for subtitle of Import Dialog
 * @constant
 */
export const IMPORT_DIALOG_SUBTITLE =
  "Upload a JSON file or select from the available community examples.";

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
