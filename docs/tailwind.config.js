module.exports = {
  content: ['./src/**/*.html', './src/**/*.js', './src/**/*.tsx'],
  corePlugins: { preflight: false, container: false },
  important: '#tailwind',
  theme: {
    extend: {
      maxWidth: {
        xxs: '18rem',
      },
    },
  },
};
