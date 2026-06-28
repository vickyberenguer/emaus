// URL del backend — en producción se sobreescribe con la variable de entorno de Netlify
const API_BASE = window.ENV_API_URL || 'http://localhost:8000';

const api = {
  async request(method, path, body = null, requiresAuth = true) {
    const headers = { 'Content-Type': 'application/json' };

    if (requiresAuth) {
      const token = sessionStorage.getItem('token');
      if (!token) {
        window.location.href = '/index.html';
        return;
      }
      headers['Authorization'] = `Bearer ${token}`;
    }

    const options = { method, headers };
    if (body) options.body = JSON.stringify(body);

    const res = await fetch(`${API_BASE}${path}`, options);

    if (res.status === 401) {
      sessionStorage.clear();
      window.location.href = '/index.html';
      return;
    }

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Error desconocido' }));
      throw new Error(err.detail || 'Error en la solicitud');
    }

    return res.json();
  },

  get:    (path)        => api.request('GET',    path),
  post:   (path, body)  => api.request('POST',   path, body),
  put:    (path, body)  => api.request('PUT',    path, body),
  delete: (path)        => api.request('DELETE', path),

  async login(email, password) {
    // Login usa form-urlencoded (OAuth2PasswordRequestForm)
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({ username: email, password }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Error al iniciar sesión' }));
      throw new Error(err.detail || 'Error al iniciar sesión');
    }
    return res.json();
  },
};
