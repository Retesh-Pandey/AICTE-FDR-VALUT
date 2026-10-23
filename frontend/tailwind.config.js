/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        vault: {
          950: '#07090e',
          900: '#0b0f16',
          850: '#0f141e',
          800: '#141c2b',
          700: '#1d273c',
          600: '#2b3955',
          border: '#1e293b',
          amber: '#f59e0b',
          'amber-glow': '#fbbf24',
          emerald: '#10b981',
          'emerald-glow': '#34d399',
          cyan: '#06b6d4',
          crimson: '#ef4444',
        }
      },
      fontFamily: {
        mono: ['"JetBrains Mono"', 'Menlo', 'monospace'],
        sans: ['Inter', 'system-ui', 'sans-serif'],
      }
    },
  },
  plugins: [],
}
