/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: { ink: '#202328', muted: '#777d87', line: '#e8e9ec', canvas: '#f7f8fa', brand: '#4e59e8' },
      boxShadow: { card: '0 8px 30px rgba(22, 28, 45, 0.045)' },
      fontFamily: { sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'] },
    },
  },
  plugins: [],
}
