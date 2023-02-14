/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,ts,tsx,jsx}"],
  important:true,
  theme: {
    extend: {},
  },
  plugins: [
    // ...
    require("@tailwindcss/forms")({
      strategy: 'class', // only generate classes
    }),
  ],
}
