/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: 'var(--color-primary)',
        'primary-hover': 'var(--color-primary-hover)',
        'primary-text': 'var(--color-primary-text)',
        secondary: 'var(--color-secondary)',
        'secondary-hover': 'var(--color-secondary-hover)',
        'secondary-text': 'var(--color-secondary-text)',
        success: 'var(--color-success)',
        danger: 'var(--color-danger)',
        'danger-hover': 'var(--color-danger-hover)',
        'danger-text': 'var(--color-danger-text)',
        warning: {
          surface: 'var(--color-warning-surface)',
          'text-on-surface': 'var(--color-warning-text-on-surface)',
        },
        background: 'var(--color-background)',
        surface: 'var(--color-surface)',
        'surface-hover': 'var(--color-surface-hover)',
        'text-primary': 'var(--color-text-primary)',
        'text-secondary': 'var(--color-text-secondary)',
        'text-accent': 'var(--color-text-accent)',
        'border-color': 'var(--color-border-color)',
      }
    },
  },
  plugins: [
    require('@tailwindcss/forms')({
      strategy: 'class', // Use classes like `form-input`, `form-checkbox`, etc.
    }),
    require('@tailwindcss/typography'),
  ],
}

