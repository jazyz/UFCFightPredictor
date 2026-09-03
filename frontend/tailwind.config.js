/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ground: "#0b0b0c",
        surface: "#151517",
        ink: "#f4f3ef",
        "ink-2": "#b8b6ae",
        muted: "#7c7a72",
        hairline: "rgba(255,255,255,0.10)",
        accent: "#e8362b",
        "accent-hover": "#f04e43",
        up: "#3ccb7f",
        down: "#ef6b62",
      },
      fontFamily: {
        display: ['"Barlow Condensed"', '"Arial Narrow"', "system-ui", "sans-serif"],
        body: ["Barlow", "system-ui", "-apple-system", '"Segoe UI"', "sans-serif"],
      },
      maxWidth: { content: "1040px" },
    },
  },
  plugins: [],
};
