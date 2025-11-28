export const convertFiles = (
  files:
    | (
        | string
        | {
            path: string;
            type: string;
            name: string;
          }
      )[]
    | undefined,
) => {
  if (!files) return [];
  return files.map((file) => {
    if (typeof file === "string") {
      return file;
    }
    return file.path;
  });
};
