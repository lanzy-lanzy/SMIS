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
                // Formal SMIS brand palette: institutional maroon + academic gold
                primary: {
                    DEFAULT: '#7B1E3B',
                    dark: '#2E0B18',
                    light: '#D05C77',
                    50: '#FCF2F4',
                    100: '#F8DFE4',
                    200: '#F0BEC9',
                    300: '#E393A5',
                    400: '#D05C77',
                    500: '#B23A54',
                    600: '#972842',
                    700: '#7B1E3B',
                    800: '#6A1A33',
                    900: '#4C1226',
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
                surface: '#F6F3F4',
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
