/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: '#0B0F19',
        surface: 'rgba(255, 255, 255, 0.03)',
        'surface-hover': 'rgba(255, 255, 255, 0.08)',
        border: 'rgba(255, 255, 255, 0.1)',
        primary: '#4338CA', // Indigo 700
        'primary-light': '#6366F1', // Indigo 500
        accent: '#38BDF8', // Sky 400
        buy: '#10B981', // Emerald 500
        'buy-dim': 'rgba(16, 185, 129, 0.2)',
        sell: '#EF4444', // Red 500
        'sell-dim': 'rgba(239, 68, 68, 0.2)',
        muted: '#94A3B8', // Slate 400
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'float': 'float 3s ease-in-out infinite',
      },
      keyframes: {
        float: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-5px)' },
        }
      },
      boxShadow: {
        'glow-buy': '0 0 15px rgba(16, 185, 129, 0.3)',
        'glow-sell': '0 0 15px rgba(239, 68, 68, 0.3)',
        'glass': '0 4px 30px rgba(0, 0, 0, 0.1)',
      },
      backdropBlur: {
        'xs': '2px',
      }
    },
  },
  plugins: [],
}
