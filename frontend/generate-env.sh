#!/bin/sh
# Genera js/env.js a partir de la variable de entorno API_URL definida en Netlify.
echo "window.ENV_API_URL = '${API_URL}';" > js/env.js
