/**
 * enum for the different types of nodes
 * @enum
 */
export enum TypeModal {
  TEXT = 1,
  PROMPT = 2,
}

export enum BuildStatus {
  BUILDING = "BUILDING",
  TO_BUILD = "TO_BUILD",
  BUILT = "BUILT",
  INACTIVE = "INACTIVE",
  ERROR = "ERROR",
}

export enum InputOutput {
  INPUT = "input",
  OUTPUT = "output",
}

export enum IOInputTypes {
  TEXT = "TextInput",
  FILE_LOADER = "FileLoader",
  KEYPAIR = "KeyPairInput",
  JSON = "JsonInput",
  STRING_LIST = "StringListInput",
}

export enum IOOutputTypes {
  TEXT = "TextOutput",
  PDF = "PDFOutput",
  CSV = "CSVOutput",
  IMAGE = "ImageOutput",
  JSON = "JsonOutput",
  KEY_PAIR = "KeyPairOutput",
  STRING_LIST = "StringListOutput",
  DATA = "DataOutput",
}

export enum EventDeliveryType {
  STREAMING = "streaming",
  POLLING = "polling",
  DIRECT = "direct",
}
