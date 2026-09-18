export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
      colors: {
        surface: {
          900: "#080c14",
          800: "#0d1220",
          700: "#121829",
          600: "#1a2235",
          500: "#232d42",
        },
        accent: {
          DEFAULT: "#3b82f6",
          glow: "#60a5fa",
          dim: "#1d4ed8",
        },
        pulse: "#22d3ee",
        warn: "#f59e0b",
        danger: "#ef4444",
        success: "#10b981",
      },
    },
  },
  plugins: [],
};
