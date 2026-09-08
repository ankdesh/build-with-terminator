/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#f0f7ff',
          100: '#e0effe',
          200: '#b9ddfd',
          500: '#1d68bd',
          600: '#13519b',
          700: '#0e3e78',
        }
      }
    },
  },
  plugins: [],
}
