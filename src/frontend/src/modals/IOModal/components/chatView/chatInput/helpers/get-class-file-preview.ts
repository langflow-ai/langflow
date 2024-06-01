export const getClassNamesFilePreview = (inputFocus) => {
  return `flex w-full items-center gap-4 rounded-t-lg bg-background px-14 py-5 overflow-auto custom-scroll ${
    inputFocus
      ? "border border-b-0 border-ring border-2"
      : "border border-b-0 border-border"
  }`;
};
