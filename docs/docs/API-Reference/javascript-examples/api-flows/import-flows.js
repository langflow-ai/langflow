const fs = require("fs");
const path = require("path");

const fixturesDir = path.join(__dirname, "../../fixtures");
const defaultFlowImport = path.join(fixturesDir, "flow-import.json");
const flowImportPath = process.env.FLOW_IMPORT_FILE || defaultFlowImport;
const flowBuf = fs.readFileSync(flowImportPath);
const flowName = path.basename(flowImportPath);

const url = `${process.env.LANGFLOW_URL ?? ""}/api/v1/flows/upload/?folder_id=${process.env.FOLDER_ID ?? ""}`;

const formData = new FormData();
formData.append("file", new Blob([flowBuf], { type: "application/json" }), flowName);

const options = {
  method: "POST",
  headers: {
    accept: "application/json",
    "x-api-key": `${process.env.LANGFLOW_API_KEY ?? ""}`,
  },
  body: formData,
};

fetch(url, options)
  .then(async (response) => {
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const text = await response.text();
    console.log(text);
  })
  .catch((error) => console.error(error));
