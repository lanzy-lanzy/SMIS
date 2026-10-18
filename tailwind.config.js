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
            },
            fontFamily: {
                sans: ['Inter', 'ui-sans-serif', 'system-ui', '-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', 'sans-serif'],
            },
            boxShadow: {
                'card': '0 1px 2px rgba(15, 23, 42, 0.05), 0 8px 24px rgba(15, 23, 42, 0.04)',
                'card-hover': '0 12px 28px rgba(15, 23, 42, 0.10)',
            }
        }
    },
    plugins: [],
}
