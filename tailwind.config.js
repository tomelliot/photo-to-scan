/** @type {import('tailwindcss').Config} */
module.exports = {
    content: [
        "./app/templates/**/*.html",
        "./app/static/app.js",
        // HTMX partials are rendered from Python string literals
        "./app/**/*.py",
    ],
};
