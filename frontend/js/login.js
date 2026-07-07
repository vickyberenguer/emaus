document.getElementById('login-form').addEventListener('submit', async (e) => {
  e.preventDefault();

  const email    = document.getElementById('email').value.trim();
  const password = document.getElementById('password').value;
  const btn      = document.getElementById('btn-login');
  const errorMsg = document.getElementById('error-msg');

  btn.disabled = true;
  btn.textContent = 'Ingresando...';
  errorMsg.classList.add('hidden');

  try {
    const data = await api.login(email, password);

    // Guardar en sessionStorage (se limpia al cerrar el navegador)
    sessionStorage.setItem('token',    data.access_token);
    sessionStorage.setItem('rol',      data.rol);
    sessionStorage.setItem('nombre',   data.nombre);
    sessionStorage.setItem('emaus_id', data.emaus_id ?? '');

    // Redirigir según rol
    const destino = {
      atl:          '/pages/relevamiento.html',
      responsable:  '/pages/control.html',
      admin:        '/pages/control.html',
    }[data.rol] || '/index.html';

    window.location.href = destino;

  } catch (err) {
    errorMsg.textContent = err.message;
    errorMsg.classList.remove('hidden');
    btn.disabled = false;
    btn.textContent = 'Ingresar';
  }
});
