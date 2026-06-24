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
                primary: '#1E3A8A',
                secondary: '#2563EB',
                accent: '#22C55E',
                danger: '#DC2626',
                warning: '#F59E0B',
            }
        }
    },
    plugins: [],
}
