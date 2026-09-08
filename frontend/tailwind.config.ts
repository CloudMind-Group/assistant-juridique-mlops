import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        display: ["var(--font-display)", "Georgia", "serif"],
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
      },
      colors: {
        forest: {
          50: "#eef3ef",
          100: "#d6e3d9",
          200: "#aec7b3",
          300: "#7fa787",
          400: "#4f7f5a",
          500: "#356643",
          600: "#26543a",
          700: "#1f4530",
          800: "#193826",
          900: "#132b1d",
          950: "#0d1f15",
        },
        sand: {
          25: "#fbfaf7",
          50: "#f7f6f1",
          100: "#f1efe7",
          200: "#e4e0d2",
          300: "#d3cbb4",
        },
        gold: {
          300: "#eecb8f",
          400: "#e0ac5c",
          500: "#cf9440",
          600: "#b17a2f",
        },
        sage: {
          300: "#a9bcae",
          400: "#8aa392",
          500: "#6c8874",
          600: "#546b5a",
        },
        sky: {
          300: "#bcd3de",
          400: "#93b7c7",
          500: "#6f9cae",
        },
        clay: {
          400: "#c96e5f",
          500: "#b5473f",
          600: "#96362f",
        },
        ink: {
          400: "#7b8279",
          500: "#5c6359",
          600: "#454c42",
          700: "#333a30",
          900: "#1a1f19",
        },
      },
      borderRadius: {
        xl: "0.875rem",
        "2xl": "1.25rem",
      },
      boxShadow: {
        card: "0 1px 2px rgba(19, 43, 29, 0.06), 0 1px 1px rgba(19, 43, 29, 0.04)",
        panel: "0 8px 24px rgba(19, 43, 29, 0.08)",
      },
      keyframes: {
        "fade-in": {
          "0%": { opacity: "0", transform: "translateY(4px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "pulse-dot": {
          "0%, 100%": { opacity: "0.35" },
          "50%": { opacity: "1" },
        },
      },
      animation: {
        "fade-in": "fade-in 0.25s ease-out",
        "pulse-dot": "pulse-dot 1.2s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};

export default config;
