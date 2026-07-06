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
                // SMIS brand palette
                primary: {
                    DEFAULT: '#1B5E20',
                    dark: '#0F3D2E',
                    light: '#4CAF50',
                    50: '#E8F5E9',
                    100: '#C8E6C9',
                    200: '#A5D6A7',
                    300: '#81C784',
                    400: '#66BB6A',
                    500: '#4CAF50',
                    600: '#43A047',
                    700: '#388E3C',
                    800: '#2E7D32',
                    900: '#1B5E20',
                },
                secondary: {
                    DEFAULT: '#1976D2',
                    50: '#E3F2FD',
                    100: '#BBDEFB',
                    500: '#2196F3',
                    700: '#1976D2',
                },
                accent: {
                    DEFAULT: '#F59E0B',
                    50: '#FFF8E1',
                    100: '#FFECB3',
                    500: '#FFC107',
                    600: '#FFB300',
                    700: '#FF8F00',
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
                surface: '#F3F4F6',
            },
            boxShadow: {
                'card': '0 1px 3px rgba(0, 0, 0, 0.08), 0 1px 2px rgba(0, 0, 0, 0.04)',
                'card-hover': '0 4px 6px rgba(0, 0, 0, 0.08), 0 2px 4px rgba(0, 0, 0, 0.04)',
            }
        }
    },
    plugins: [],
}
