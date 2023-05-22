/** @type {import('tailwindcss').Config} */
import plugin from "tailwindcss/plugin";
module.exports = {
  content: ["./index.html", "./src/**/*.{js,ts,tsx,jsx}"],
  darkMode: "class",
  important: true,
  theme: {
    extend: {
      borderColor: {
        "red-outline": "rgba(255, 0, 0, 0.8)",
        "green-outline": "rgba(72, 187, 120, 0.7)",
      },
      boxShadow: {
        "red-outline": "0 0 5px rgba(255, 0, 0, 0.5)",
        "green-outline": "0 0 5px rgba(72, 187, 120, 0.7)",
      },

      animation: {
        "pulse-green": "pulseGreen 1s linear",
      },
      keyframes: {
        pulseGreen: {
          "0%": { boxShadow: "0 0 0 0 rgba(72, 187, 120, 0.7)" },
          "100%": { boxShadow: "0 0 0 10px rgba(72, 187, 120, 0)" },
        },
      },
    },
  },
  plugins: [
    require("@tailwindcss/forms")({
      strategy: "class", // only generate classes
    }),
    plugin(function ({ addUtilities }) {
      addUtilities({
        ".scrollbar-hide": {
          /* IE and Edge */
          "-ms-overflow-style": "none",
          /* Firefox */
          "scrollbar-width": "none",
          /* Safari and Chrome */
          "&::-webkit-scrollbar": {
            display: "none",
          },
        },
        ".arrow-hide": {
          "&::-webkit-inner-spin-button": {
            "-webkit-appearance": "none",
            margin: 0,
          },
          "&::-webkit-outer-spin-button": {
            "-webkit-appearance": "none",
            margin: 0,
          },
        },
        ".password": {
          "-webkit-text-security": "disc",
          "font-family": "text-security-disc",
        },
        ".stop": {
          "-webkit-animation-play-state": "paused",
          "-moz-animation-play-state": "paused",
          "animation-play-state": "paused",
        },
        ".custom-scroll": {
          "&::-webkit-scrollbar": {
            width: "8px",
          },
          "&::-webkit-scrollbar-track": {
            backgroundColor: "#f1f1f1",
          },
          "&::-webkit-scrollbar-thumb": {
            backgroundColor: "#ccc",
            borderRadius: "999px",
          },
          "&::-webkit-scrollbar-thumb:hover": {
            backgroundColor: "#bbb",
          },
        },
        ".dark .theme-attribution .react-flow__attribution": {
          backgroundColor: "rgba(255, 255, 255, 0.2)",
        },
        ".dark .theme-attribution .react-flow__attribution a": {
          color: "black",
        },
      });
    }),
    require("@tailwindcss/typography"),
  ],
};
