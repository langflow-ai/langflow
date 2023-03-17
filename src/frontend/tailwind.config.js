/** @type {import('tailwindcss').Config} */
const plugin = require('tailwindcss/plugin')
module.exports = {
  content: ["./src/**/*.{js,ts,tsx,jsx}"],
  darkMode: 'class',
  important:true,
  theme: {
    extend: {},
  },
  plugins: [
    require("@tailwindcss/forms")({
      strategy: 'class', // only generate classes
    }),
    plugin(function ({ addUtilities }) {
      addUtilities({
        '.scrollbar-hide': {
          /* IE and Edge */
          '-ms-overflow-style': 'none',
          /* Firefox */
          'scrollbar-width': 'none',
          /* Safari and Chrome */
          '&::-webkit-scrollbar': {
            display: 'none'
          }
        },
        '.arrow-hide':{
          '&::-webkit-inner-spin-button':{
            '-webkit-appearance': 'none',
            'margin': 0
          },
          '&::-webkit-outer-spin-button':{
            '-webkit-appearance': 'none',
            'margin': 0
          },
        },
        '.password':{
          "-webkit-text-security":"disc"
        }
      }
      )
    })
  ],
}
