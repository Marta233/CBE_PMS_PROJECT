/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        display: ['Cormorant Garamond', 'Georgia', 'serif'],
        login: ['Manrope', 'system-ui', 'sans-serif'],
      },
      colors: {
        brand: {
          50:  '#f9eefa',
          100: '#f0d4f3',
          200: '#e0a9e7',
          300: '#cc77d8',
          400: '#b04ec4',
          500: '#892d8f',
          600: '#6e2473',
          700: '#541b58',
          800: '#3a123d',
          900: '#200922',
        },
        gold: {
          300: '#e8c996',
          400: '#d4a574',
          500: '#c4894a',
          600: '#a86f35',
        },
      },
      animation: {
        'fade-in': 'fadeIn 0.25s ease-out',
        'slide-up': 'slideUp 0.25s ease-out',
        'liquid-1': 'liquidMorph1 18s ease-in-out infinite',
        'liquid-2': 'liquidMorph2 22s ease-in-out infinite',
        'liquid-3': 'liquidMorph3 26s ease-in-out infinite',
        'float-soft': 'floatSoft 8s ease-in-out infinite',
        'login-rise': 'loginRise 0.7s cubic-bezier(0.22, 1, 0.36, 1) both',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        liquidMorph1: {
          '0%, 100%': { borderRadius: '60% 40% 30% 70% / 60% 30% 70% 40%', transform: 'translate(0, 0) rotate(0deg)' },
          '33%': { borderRadius: '30% 60% 70% 40% / 50% 60% 30% 60%', transform: 'translate(4%, -3%) rotate(8deg)' },
          '66%': { borderRadius: '50% 60% 30% 60% / 30% 40% 70% 60%', transform: 'translate(-3%, 4%) rotate(-4deg)' },
        },
        liquidMorph2: {
          '0%, 100%': { borderRadius: '40% 60% 70% 30% / 40% 40% 60% 50%', transform: 'translate(0, 0) scale(1)' },
          '50%': { borderRadius: '70% 30% 40% 60% / 60% 40% 60% 40%', transform: 'translate(-5%, 3%) scale(1.05)' },
        },
        liquidMorph3: {
          '0%, 100%': { borderRadius: '50% 50% 40% 60% / 40% 60% 50% 50%', transform: 'translate(0, 0)' },
          '50%': { borderRadius: '60% 40% 60% 40% / 50% 30% 70% 50%', transform: 'translate(6%, -2%)' },
        },
        floatSoft: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-10px)' },
        },
        loginRise: {
          '0%': { opacity: '0', transform: 'translateY(18px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
    },
  },
  plugins: [],
};
