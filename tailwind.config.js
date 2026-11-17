/** @type {import('tailwindcss').Config} */
// Сборка: tools\tailwindcss.exe -i static/css/tailwind.input.css -o static/css/tailwind.css --minify
// Конфиг повторяет настройки Play CDN из templates/base.html (см. docs/DESIGN.md).
module.exports = {
  darkMode: "class",
  corePlugins: { preflight: false }, // legacy app.css уже задаёт базу; включить после полной миграции
  content: ["./templates/**/*.html", "./static/js/**/*.js"],
  theme: {
    extend: {
      colors: {
        charcoal: { 500: "#4a4032", 600: "#3a3228", 700: "#2b251d", 800: "#211c16", 900: "#171310" },
        sand: { 50: "#faf6ef", 100: "#f3ecdf", 200: "#e7dcc7", 300: "#d9c9a8" },
        brass: { 400: "#d3a44a", 500: "#c08b2d", 600: "#a37422", 700: "#7d5a1a" },
        terra: { 400: "#d0705a", 500: "#c4573a", 600: "#a8462e", 700: "#873523" },
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        display: ["Georgia", "Times New Roman", "serif"],
      },
    },
  },
  plugins: [],
};
