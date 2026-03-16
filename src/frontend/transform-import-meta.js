// Custom Jest transformer to replace import.meta.env with process.env
const tsJest = require("ts-jest").default;

module.exports = {
  createTransformer() {
    const tsJestTransformer = tsJest.createTransformer();

    return {
      ...tsJestTransformer,
      process(sourceText, sourcePath, options) {
        // Replace import.meta.env with process.env before ts-jest processes it
        let modifiedSource = sourceText.replace(
          /import\.meta\.env/g,
          "process.env",
        );

        // Call the original ts-jest transformer
        return tsJestTransformer.process(modifiedSource, sourcePath, options);
      },
    };
  },
};
