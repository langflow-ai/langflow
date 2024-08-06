export async function createFileUpload(props?: {
  accept?: string;
  multiple?: boolean;
}): Promise<File[]> {
  let lock = false;
  return new Promise((resolve) => {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = props?.accept ?? ".json";
    input.multiple = props?.multiple ?? true;
    input.style.display = "none";
    // add a change event listener to the file input
    input.onchange = async (e: Event) => {
      lock = true;
      resolve(Array.from((e.target as HTMLInputElement).files!));
      document.body.removeChild(input);
    };
    window.addEventListener(
      "focus",
      () => {
        setTimeout(() => {
          if (!lock) {
            resolve([]);
            document.body.removeChild(input);
          }
        }, 300);
      },
      { once: true },
    );
    // add the input element to the body to ensure it is part of the DOM
    document.body.appendChild(input);
    // trigger the file input click event to open the file dialog
    input.click();
  });
}
