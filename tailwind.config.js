/** @type {import('tailwindcss').Config} */
module.exports = {
    darkMode: 'class',
    content: [
        './templates/**/*.html',
        './**/templates/**/*.html',
        // Widget classes live in form definitions, not templates.
        './accounts/forms.py',
        './academics/forms.py',
        './students/forms.py',
    ],
    theme: {
        extend: {
            colors: {
                // Institutional navy + golden-yellow palette shared by every template
                primary: {
                    DEFAULT: '#1B2A5B',
                    dark: '#121D3F',
                    light: '#5F7FD3',
                    50: '#F1F5FD',
                    100: '#E0E8F9',
                    200: '#C2D1F1',
                    300: '#97AEE5',
                    400: '#6486D4',
                    500: '#3A5FC4',
                    600: '#2A47A6',
                    700: '#203C8C',
                    800: '#1B2A5B',
                    900: '#121D3F',
                },
                secondary: {
                    DEFAULT: '#2F6FE0',
                    50: '#EFF5FE',
                    100: '#DCEAFD',
                    500: '#4B85E8',
                    700: '#1F55B8',
                },
                accent: {
                    DEFAULT: '#F7C93E',
                    50: '#FFFBEB',
                    100: '#FEF3C7',
                    500: '#FBCB3B',
                    600: '#E9B723',
                    700: '#A16207',
                },
                danger: {
                    DEFAULT: '#EF4444',
                    50: '#FFEBEE',
                    100: '#FFCDD2',
                    500: '#F44336',
                    600: '#E53935',
                    700: '#D32F2F',
                },
                purple: {
                    DEFAULT: '#9333EA',
                    50: '#F3E5F5',
                    100: '#E1BEE7',
                    500: '#9C27B0',
                    600: '#8E24AA',
                    700: '#7B1FA2',
                },
                surface: '#F2F5FA',
                glass: {
                    DEFAULT: 'rgba(255, 255, 255, 0.58)',
                    strong: 'rgba(255, 255, 255, 0.76)',
                    weak: 'rgba(255, 255, 255, 0.40)',
                    dark: 'rgba(20, 30, 54, 0.55)',
                },
                ink: {
                    DEFAULT: '#0F172A',
                    muted: '#5B6A85',
                    soft: '#8492AB',
                },
            },
            fontFamily: {
                sans: ['Inter', 'ui-sans-serif', 'system-ui', '-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', 'sans-serif'],
            },
            boxShadow: {
                'card': '0 12px 36px -14px rgba(15, 23, 42, 0.20), 0 2px 6px -2px rgba(15, 23, 42, 0.08)',
                'card-hover': '0 30px 80px -28px rgba(15, 23, 42, 0.38), 0 6px 18px -8px rgba(15, 23, 42, 0.14)',
                'glass': '0 12px 36px -14px rgba(15, 23, 42, 0.20), 0 2px 6px -2px rgba(15, 23, 42, 0.08)',
                'glass-lg': '0 30px 80px -28px rgba(15, 23, 42, 0.38), 0 6px 18px -8px rgba(15, 23, 42, 0.14)',
                'neu': '9px 9px 20px rgba(116, 138, 174, 0.26), -9px -9px 20px rgba(255, 255, 255, 0.88)',
                'neu-sm': '4px 4px 10px rgba(116, 138, 174, 0.24), -4px -4px 10px rgba(255, 255, 255, 0.82)',
                'neu-inset': 'inset 4px 4px 9px rgba(116, 138, 174, 0.24), inset -4px -4px 9px rgba(255, 255, 255, 0.86)',
            },
            borderRadius: {
                'glass': '1.25rem',
            },
            transitionTimingFunction: {
                liquid: 'cubic-bezier(0.22, 0.61, 0.36, 1)',
            },
        }
    },
    plugins: [],
}
