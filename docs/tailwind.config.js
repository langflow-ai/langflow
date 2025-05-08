/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{js,jsx,ts,tsx,md,mdx}",
    "./docs/**/*.{js,jsx,ts,tsx,md,mdx}",
    "./blog/**/*.{js,jsx,ts,tsx,md,mdx}",
  ],
  theme: {
    extend: {},
  },
  plugins: [],
  // Docusaurus specific configuration
  corePlugins: {
    preflight: false, // This is important to prevent Tailwind from conflicting with Docusaurus styles
  },
  darkMode: ['class', '[data-theme="dark"]'], // This helps with Docusaurus dark mode
}
