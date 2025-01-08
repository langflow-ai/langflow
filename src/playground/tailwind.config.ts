import type { Config } from 'tailwindcss';
import frontendConfig from '../frontend/tailwind.config.mjs';

const config: Config = {
  darkMode: ["class"],
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
    "../frontend/src/components/**/*.{js,ts,jsx,tsx}",
  ],
  theme: frontendConfig.theme,
  plugins: frontendConfig.plugins,
};

export default config;
