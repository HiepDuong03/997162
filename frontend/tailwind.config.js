/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: { 950: "#0a0a0c", 900: "#101014", 850: "#16161c", 800: "#1c1c24", 700: "#2a2a34" },
        line: "#26262f",
        accent: { DEFAULT: "#6366f1", hover: "#7c7ef2" },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
