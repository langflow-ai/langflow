const config = {
  plugins: ["prettier-plugin-organize-imports", "prettier-plugin-tailwindcss"],
  tailwindConfig: "./tailwind.config.mjs",
  organizeImportsSkipDestructiveCodeActions: true,
};

export default config;
