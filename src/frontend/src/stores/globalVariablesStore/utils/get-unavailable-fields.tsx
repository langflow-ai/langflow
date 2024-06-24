export default function getUnavailableFields(variables: {
  [key: string]: { default_fields?: string[] };
}): { [name: string]: string } {
  const unVariables: { [name: string]: string } = {};
  Object.keys(variables).forEach((key) => {
    if (variables[key].default_fields) {
      variables[key].default_fields!.forEach((field) => {
        unVariables[field] = key;
      });
    }
  });
  return unVariables;
}
