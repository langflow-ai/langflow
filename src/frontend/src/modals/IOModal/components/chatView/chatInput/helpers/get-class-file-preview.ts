export const getClassNamesFilePreview = (inputFocus) => {
  return `flex w-full items-center gap-4 rounded-t-lg bg-background px-14 py-5 overflow-auto custom-scroll border  ${
    inputFocus ? "border-ring" : ""
  }`;
};
