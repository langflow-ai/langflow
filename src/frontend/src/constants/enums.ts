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
