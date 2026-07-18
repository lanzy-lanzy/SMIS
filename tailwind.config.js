/** @type {import('tailwindcss').Config} */
module.exports = {
    darkMode: 'class',
    content: [
        './templates/**/*.html',
        './**/templates/**/*.html',
    ],
    theme: {
        extend: {
            colors: {
                // Formal SMIS brand palette: institutional navy + academic blue
                primary: {
                    DEFAULT: '#1D4ED8',
                    dark: '#0B1F33',
                    light: '#60A5FA',
                    50: '#EFF6FF',
                    100: '#DBEAFE',
                    200: '#BFDBFE',
                    300: '#93C5FD',
                    400: '#60A5FA',
                    500: '#3B82F6',
                    600: '#2563EB',
                    700: '#1D4ED8',
                    800: '#1E40AF',
                    900: '#1E3A8A',
                },
                secondary: {
                    DEFAULT: '#0F766E',
                    50: '#F0FDFA',
                    100: '#CCFBF1',
                    500: '#14B8A6',
                    700: '#0F766E',
                },
                accent: {
                    DEFAULT: '#C68A1B',
                    50: '#FFFBEB',
                    100: '#FEF3C7',
                    500: '#D5A12A',
                    600: '#C68A1B',
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
                surface: '#F4F6F9',
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
