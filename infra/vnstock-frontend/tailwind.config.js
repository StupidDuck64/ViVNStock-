/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        up: "#26a69a",
        down: "#ef5350",
        bg: {
          primary: "#131722",
          secondary: "#1e222d",
          tertiary: "#2a2e39",
        },
        text: {
          primary: "#d1d4dc",
          secondary: "#787b86",
        },
      },
    },
  },
  plugins: [],
};
