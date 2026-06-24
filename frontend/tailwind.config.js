/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          carbon: 'var(--ff-color-brand-carbon)',
          ink: 'var(--ff-color-brand-ink)',
          slate: 'var(--ff-color-brand-slate)',
          teal: 'var(--ff-color-brand-teal)',
          flow: 'var(--ff-color-brand-flow)',
          mint: 'var(--ff-color-brand-mint)',
        },
        surface: {
          page: 'var(--ff-color-surface-page)',
          card: 'var(--ff-color-surface-card)',
        },
        border: {
          subtle: 'var(--ff-color-border-subtle)',
        },
        status: {
          success: {
            DEFAULT: 'var(--ff-color-status-success)',
            soft: 'var(--ff-color-status-success-soft)',
          },
          warning: {
            DEFAULT: 'var(--ff-color-status-warning)',
            soft: 'var(--ff-color-status-warning-soft)',
          },
          danger: {
            DEFAULT: 'var(--ff-color-status-danger)',
            soft: 'var(--ff-color-status-danger-soft)',
          },
          info: {
            DEFAULT: 'var(--ff-color-status-info)',
            soft: 'var(--ff-color-status-info-soft)',
          },
        },
        primary: {
          50: '#eff6ff',
          100: '#dbeafe',
          200: '#bfdbfe',
          300: '#93c5fd',
          400: '#60a5fa',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
          800: '#1e40af',
          900: '#1e3a8a',
        },
        // Colores de ARCA/Argentina
        celeste: '#74acdf',
        sol: '#f6b40e',
      },
      borderRadius: {
        control: 'var(--ff-radius-control)',
        panel: 'var(--ff-radius-panel)',
        modal: 'var(--ff-radius-modal)',
      },
      boxShadow: {
        panel: 'var(--ff-shadow-panel)',
        overlay: 'var(--ff-shadow-overlay)',
      },
    },
  },
  plugins: [],
}
