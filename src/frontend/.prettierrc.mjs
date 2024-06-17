const config = {
  plugins: ["prettier-plugin-tailwindcss", "prettier-plugin-organize-imports"],
  tailwindConfig: "./tailwind.config.mjs",
  organizeImportsSkipDestructiveCodeActions: true,
};

export default config;
