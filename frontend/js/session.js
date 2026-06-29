const session = {
  token:   () => sessionStorage.getItem('token'),
  rol:     () => sessionStorage.getItem('rol'),
  nombre:  () => sessionStorage.getItem('nombre'),
  emausId: () => sessionStorage.getItem('emaus_id') || null,

  requireRol(rolesPermitidos) {
    if (!this.token() || !rolesPermitidos.includes(this.rol())) {
      window.location.href = '/index.html';
    }
  },

  logout() {
    sessionStorage.clear();
    window.location.href = '/index.html';
  },

  pintarNavbar(tituloSeccion) {
    const el = document.getElementById('navbar-info');
    if (el) {
      el.innerHTML = `
        <span class="text-white-50 small me-3">${tituloSeccion}</span>
        <span class="text-white small me-3"><i class="bi bi-person-circle"></i> ${this.nombre() || ''}</span>
        <button class="btn btn-sm btn-outline-light" onclick="session.logout()">
          <i class="bi bi-box-arrow-right"></i> Salir
        </button>`;
    }
  },
};
