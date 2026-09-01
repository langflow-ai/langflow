const fs = require("fs");
const path = require("path");

const fixturesDir = path.join(__dirname, "../../fixtures");
const defaultUpload = path.join(fixturesDir, "sample-upload.txt");
const uploadPath = process.env.SAMPLE_UPLOAD_FILE || defaultUpload;
const uploadBuf = fs.readFileSync(uploadPath);
const uploadName = path.basename(uploadPath);

const url = `${process.env.LANGFLOW_URL ?? ""}/api/v2/files`;

const formData = new FormData();
formData.append("file", new Blob([uploadBuf]), uploadName);

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
