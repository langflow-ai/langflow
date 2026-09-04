// Extension components carry a namespaced ``data.type`` of the form
// ``ext:<bundle>:<ClassName>@<slot>``.  Test IDs historically embed the bare
// class name (``output-inspection-<title>-<ClassName>``,
// ``handle-<type>-<shownode>-<field>-<side>``); without this strip, extension
// components would yield verbose IDs containing ``:`` and ``@`` that diverge
// from the built-in convention.
export const classNameFromType = (type: string): string => {
  const match = type.match(/^ext:[^:]+:([^@]+)@.+$/);
  return match?.[1] ?? type;
};

export default classNameFromType;
