const fs = require("fs");
const path = require("path");

const fixturesDir = path.join(__dirname, "../../fixtures");
const defaultImage = path.join(fixturesDir, "sample-upload.png");
const imagePath = process.env.SAMPLE_IMAGE_FILE || defaultImage;
const imageBuf = fs.readFileSync(imagePath);
const imageName = path.basename(imagePath);

const url = `${process.env.LANGFLOW_URL ?? ""}/api/v1/files/upload/${process.env.FLOW_ID ?? ""}`;

const formData = new FormData();
formData.append("file", new Blob([imageBuf]), imageName);

const options = {
  method: "POST",
  headers: {
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
