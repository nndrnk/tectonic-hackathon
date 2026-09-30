/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#172b3a",
        paper: "#f5f7f8",
        trust: {
          green: "#147d64",
          amber: "#b86612",
          red: "#b83b4b",
        },
      },
      boxShadow: {
        card: "0 12px 40px rgba(23, 43, 58, 0.08)",
      },
    },
  },
  plugins: [],
};
