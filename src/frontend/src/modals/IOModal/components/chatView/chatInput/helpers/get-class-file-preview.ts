export const getClassNamesFilePreview = (inputFocus) => {
  return `flex w-full items-center gap-2 rounded-t-md bg-background px-10 py-5 ${
    inputFocus
      ? "border-2 border-b-0 border-ring"
      : "border border-b-0 border-border"
  }`;
};
