/**
 * Generates a unique variable name for the prompt template.
 * If "variable_name" doesn't exist, returns it.
 * Otherwise, returns "variable_name_1", "variable_name_2", etc.
 */
export const generateUniqueVariableName = (
  templateValue: string,
  isDoubleBrackets: boolean = false,
): string => {
  // Match both single {var} and double {{var}} bracket patterns
  const variableRegex = isDoubleBrackets
    ? /\{\{([a-zA-Z_][a-zA-Z0-9_]*)\}\}/g
    : /\{([^{}]+)\}/g;
  const existingVariables = new Set<string>();
  let match: RegExpExecArray | null = variableRegex.exec(templateValue);
  while (match !== null) {
    existingVariables.add(match[1]);
    match = variableRegex.exec(templateValue);
  }

  let variableName = "variable_name";
  if (existingVariables.has(variableName)) {
    let counter = 1;
    while (existingVariables.has(`variable_name_${counter}`)) {
      counter++;
    }
    variableName = `variable_name_${counter}`;
  }

  return variableName;
};
