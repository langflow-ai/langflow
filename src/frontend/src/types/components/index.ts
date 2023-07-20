import { ReactElement, ReactNode } from "react";
import { APIClassType } from "../api";
import { NodeDataType } from "../flow/index";
import { typesContextType } from "../typesContext";

export type InputComponentType = {
  value: string;
  disabled?: boolean;
  onChange: (value: string) => void;
  password: boolean;
  disableCopyPaste?: boolean;
  editNode?: boolean;
  onChangePass?: (value: boolean | boolean) => void;
  showPass?: boolean;
};
export type ToggleComponentType = {
  enabled: boolean;
  setEnabled: (state: boolean) => void;
  disabled: boolean;
  size: "small" | "medium" | "large";
};
export type DropDownComponentType = {
  value: string;
  options: string[];
  onSelect: (value: string) => void;
  editNode?: boolean;
  apiModal?: boolean;
  numberOfOptions?: number;
};
export type ParameterComponentType = {
  data: NodeDataType;
  title: string;
  id: string;
  color: string;
  left: boolean;
  type: string;
  required?: boolean;
  name?: string;
  tooltipTitle: string;
  dataContext?: typesContextType;
  optionalHandle?: Array<String>;
  info?: string;
};
export type InputListComponentType = {
  value: string[];
  onChange: (value: string[]) => void;
  disabled: boolean;
  editNode?: boolean;
  onAddInput?: (value?: string[]) => void;
};

export type TextAreaComponentType = {
  field_name?: string;
  nodeClass?: APIClassType;
  setNodeClass?: (value: APIClassType) => void;
  disabled: boolean;
  onChange: (value: string[] | string) => void;
  value: string;
  editNode?: boolean;
};

export type CodeAreaComponentType = {
  disabled: boolean;
  onChange: (value: string[] | string) => void;
  value: string;
  editNode?: boolean;
  nodeClass: APIClassType;
  setNodeClass: (value: APIClassType) => void;
};

export type FileComponentType = {
  disabled: boolean;
  onChange: (value: string[] | string) => void;
  value: string;
  suffixes: Array<string>;
  fileTypes: Array<string>;
  onFileChange: (value: string) => void;
  editNode?: boolean;
};

export type DisclosureComponentType = {
  children: ReactNode;
  openDisc: boolean;
  button: {
    title: string;
    Icon: any;
    buttons?: {
      Icon: ReactElement;
      title: string;
      onClick: (event?: React.MouseEvent) => void;
    }[];
  };
};
export type FloatComponentType = {
  value: string;
  disabled?: boolean;
  disableCopyPaste?: boolean;
  onChange: (value: string) => void;
  editNode?: boolean;
};

export type TooltipComponentType = {
  children: ReactElement;
  title: string | ReactElement;
  placement?:
    | "bottom-end"
    | "bottom-start"
    | "bottom"
    | "left-end"
    | "left-start"
    | "left"
    | "right-end"
    | "right-start"
    | "right"
    | "top-end"
    | "top-start"
    | "top";
};

export type ProgressBarType = {
  children?: ReactElement;
  value?: number;
  max?: number;
};

export type RadialProgressType = {
  value?: number;
  color?: string;
};

export type AccordionComponentType = {
  children?: ReactElement;
  open?: string[];
  trigger?: string | ReactElement;
  keyValue?: string;
};
export type Side = "top" | "right" | "bottom" | "left";

export type ShadTooltipProps = {
  delayDuration?: number;
  side?: Side;
  content: ReactNode;
  children: ReactNode;
  style?: string;
};
export type ShadToolTipType = {
  content?: ReactNode;
  side?: "top" | "right" | "bottom" | "left";
  asChild?: boolean;
  children?: ReactElement;
  delayDuration?: number;
  styleClasses?: string;
};

export type TextHighlightType = {
  value?: string;
  side?: "top" | "right" | "bottom" | "left";
  asChild?: boolean;
  children?: ReactElement;
  delayDuration?: number;
};

export interface IVarHighlightType {
  name: string;
}

export type IconComponentProps = {
  name: string;
  className: string;
  iconColor?: string;
};

export type InputProps = {
  name: string | null;
  description: string | null;
  maxLength?: number;
  flows: Array<{ id: string; name: string }>;
  tabId: string;
  setName: (name: string) => void;
  setDescription: (description: string) => void;
  updateFlow: (flow: { id: string; name: string }) => void;
};

export type TooltipProps = {
  selector: string;
  content?: string;
  disabled?: boolean;
  htmlContent?: React.ReactNode;
  className?: string; // This should use !impornant to override the default styles eg: '!bg-white'
  position?: "top" | "right" | "bottom" | "left";
  clickable?: boolean;
  children: React.ReactNode;
  delayShow?: number;
};

export type LoadingComponentProps = {
  remSize: number;
};

export type ContentProps = { children: ReactNode };
export type HeaderProps = { children: ReactNode; description: string };

export interface languageMap {
  [key: string]: string | undefined;
}

export type groupedObjType = {
  component: string;
  family: string;
  type: string;
};

export type dataObjType = {
  base_classes: string[];
  custom_fields: object;
  description: string;
  display_name: string;
  documentation: string;
  output_types: Array<void | string>;
  template: object;
};

export type documentloadersType = {
  AZLyricsLoader: dataObjType;
  AirbyteJSONLoader: dataObjType;
  BSHTMLLoader: dataObjType;
  CSVLoader: dataObjType;
  CoNLLULoader: dataObjType;
  CollegeConfidentialLoader: dataObjType; 
  DirectoryLoader: dataObjType;
  EverNoteLoader: dataObjType;
  FacebookChatLoader: dataObjType;
  GitLoader: dataObjType;
  GitbookLoader: dataObjType;
  GutenbergLoader: dataObjType;
  HNLoader: dataObjType;
  IFixitLoader: dataObjType;
  IMSDbLoader: dataObjType;
  NotionDirectoryLoader: dataObjType;
  PyPDFDirectoryLoader: dataObjType;
  PyPDFLoader: dataObjType;
  ReadTheDocsLoader: dataObjType;
  SRTLoader: dataObjType;
  SlackDirectoryLoader: dataObjType;
  TextLoader: dataObjType;
  UnstructuredEmailLoader: dataObjType;
  UnstructuredHTMLLoader: dataObjType;
  UnstructuredMarkdownLoader: dataObjType;
  UnstructuredPowerPointLoader: dataObjType;
  UnstructuredWordDocumentLoader: dataObjType;
  WebBaseLoader: dataObjType;
};

export type agentsType = {
  AgentInitializer: dataObjType;
  CSVAgent: dataObjType;
  JsonAgent: dataObjType;
  SQLAgent: dataObjType;
  VectorStoreAgent: dataObjType;
  VectorStoreRouterAgent: dataObjType;
  ZeroShotAgent: dataObjType;
};

export type chainsType = {
  CombineDocsChain: dataObjType;
  ConversationChain: dataObjType;
  ConversationalRetrievalChain: dataObjType;
  LLMChain: dataObjType;
  LLMCheckerChain: dataObjType;
  LLMMathChain: dataObjType;
  MidJourneyPromptChain: dataObjType;
  RetrievalQA: dataObjType
  RetrievalQAWithSourcesChain: dataObjType;
  SQLDatabaseChain: dataObjType;
  SeriesCharacterChain: dataObjType;
  TimeTravelGuideChain: dataObjType;
}

export type embeddingsType = {
  CohereEmbeddings: dataObjType;
  HuggingFaceEmbeddings: dataObjType;
  OpenAIEmbeddings: dataObjType;
};

export type llmsTypes = {
  Anthropic: dataObjType;
  CTransformers: dataObjType;
  ChatAnthropic: dataObjType;
  ChatOpenAI: dataObjType;
  Cohere: dataObjType;
  HuggingFaceHub: dataObjType;
  LlamaCpp: dataObjType;
  OpenAI: dataObjType;
  VertexAI: dataObjType;
}

export type memoriesType = {
  ConversationBufferMemory: dataObjType;
  ConversationBufferWindowMemory: dataObjType;
  ConversationEntityMemory: dataObjType;
  ConversationKGMemory: dataObjType;
  ConversationSummaryMemory: dataObjType;
  MongoDBChatMessageHistory: dataObjType;
  PostgresChatMessageHistory: dataObjType;
  VectorStoreRetrieverMemory: dataObjType;
};

export type outputParsersType = {
  ResponseSchema: dataObjType;
  StructuredOutputParser: dataObjType;
};

export type promptsType = {
  ChatMessagePromptTemplate: dataObjType;
  ChatPromptTemplate: dataObjType;
  HumanMessagePromptTemplate: dataObjType;
  PromptTemplate: dataObjType;
  SystemMessagePromptTemplate: dataObjType;
}

export type retrieversType = {
  MultiQueryRetriever: dataObjType;
};

export type textSplittersType = {
  CharacterTextSplitter: dataObjType;
  RecursiveCharacterTextSplitter: dataObjType;
};

export type toolkitsType = {
  JsonToolkit: dataObjType;
  OpenAPIToolkit: dataObjType;
  VectorStoreInfo: dataObjType;
  VectorStoreRouterToolkit: dataObjType;
  VectorStoreToolkit: dataObjType;
};

export type toolsType = {
  BingSearchRun: dataObjType;
  Calculator: dataObjType;
  GoogleSearchResults: dataObjType;
  GoogleSearchRun: dataObjType;
  GoogleSerperRun: dataObjType;
  InfoSQLDatabaseTool: dataObjType;
  JsonGetValueTool: dataObjType;
  JsonListKeysTool: dataObjType;
  JsonSpec: dataObjType;
  ListSQLDatabaseTool: dataObjType;
  "News API": dataObjType;
  'PAL-MATH': dataObjType;
  "Podcast API": dataObjType;
  PythonAstREPLTool: dataObjType;
  PythonFunction: dataObjType;
  PythonFunctionTool: dataObjType;
  PythonREPLTool: dataObjType;
  QuerySQLDataBaseTool: dataObjType;
  RequestsDeleteTool: dataObjType;
  RequestsGetTool: dataObjType;
  RequestsPatchTool: dataObjType;
  RequestsPostTool: dataObjType;
  RequestsPutTool: dataObjType;
  Search: dataObjType;
  'TMDB API': dataObjType;
  Tool: dataObjType;
  WikipediaQueryRun: dataObjType;
  WolframAlphaQueryRun: dataObjType;
};

export type utilitiesType = {
  BingSearchAPIWrapper: dataObjType;
  GoogleSearchAPIWrapper: dataObjType;
  GoogleSerperAPIWrapper: dataObjType;
  SearxSearchWrapper: dataObjType;
  SerpAPIWrapper: dataObjType;
  WikipediaAPIWrapper: dataObjType;
  WolframAlphaAPIWrapper: dataObjType;
};

export type vectorStoresType = {
  Chroma: dataObjType;
  FAISS: dataObjType;
  MongoDBAtlasVectorSearch: dataObjType;
  Pinecone: dataObjType;
  Qdrant: dataObjType;
  SupabaseVectorStore: dataObjType;
  Weaviate: dataObjType;
};

export type wrappersType = {
  SQLDatabase: dataObjType;
  TextRequestsWrapper: dataObjType; 
};

export type dataType = {
  agents?: agentsType;
  chains?: chainsType;
  documentloaders?: documentloadersType;
  embeddings?: embeddingsType;
  llms?: llmsTypes;
  memories?: memoriesType;
  output_parsers?: outputParsersType;
  prompts?: promptsType;
  retrievers?: retrieversType;
  textsplitters?: textSplittersType;
  toolkits?: toolkitsType;
  tools?: toolsType
  utilities?: utilitiesType;
  vectorstores?: vectorStoresType;
  wrappers?: wrappersType;
};

export type tweakType = {
  "ChatOpenAI-TxuiN": object;
  "LLMChain-zPC3w": object;
  "PromptTemplate-iNj5W": object;
  "ConversationBufferMemory-JnodM": object;
}
