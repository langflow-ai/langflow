const fs = require("fs");
const path = require("path");

const fixturesDir = path.join(__dirname, "../../fixtures");
const defaultProjectZip = path.join(fixturesDir, "project-import.zip");
const projectPath = process.env.PROJECT_IMPORT_FILE || defaultProjectZip;
const projectBuf = fs.readFileSync(projectPath);
const projectName = path.basename(projectPath);

const url = `${process.env.LANGFLOW_URL ?? ""}/api/v1/projects/upload/`;

const formData = new FormData();
formData.append("file", new Blob([projectBuf], { type: "application/zip" }), projectName);

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
