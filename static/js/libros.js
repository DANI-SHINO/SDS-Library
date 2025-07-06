// Execute when the DOM is fully loaded
document.addEventListener("DOMContentLoaded", function () {

  // Delegation for the Edit button: replaces the main content dynamically
  document.addEventListener("click", function (e) {
    // Check if the clicked element or its parent has the class 'btn-editar'
    if (e.target.closest(".btn-editar")) {
      // Get the button element
      const btn = e.target.closest(".btn-editar");

      // Get the book ID from data attribute
      const libroId = btn.getAttribute("data-id");

      // Get the container where the content will be replaced
      const contenedor = document.getElementById("contenido-principal");

      // Show a loading spinner while fetching
      contenedor.innerHTML = `
        <div class="d-flex justify-content-center align-items-center p-4">
          <div class="spinner-border text-primary" role="status">
            <span class="visually-hidden">Cargando...</span>
          </div>
        </div>
      `;

      // Fetch the edit form HTML and insert it
      fetch(`/admin/libros/editar/${libroId}`)
        .then(res => res.text())
        .then(html => {
          contenedor.innerHTML = html;

          // Add fade-in transition effect
          contenedor.style.opacity = 0;
          contenedor.style.transition = "opacity 0.3s ease";
          setTimeout(() => contenedor.style.opacity = 1, 10);
        });
    }
  });

  // Live filter for the books table
  document.getElementById("busqueda-libro").addEventListener("keyup", function () {
    // Get the search value in lowercase
    const filtro = this.value.toLowerCase();

    // Get all rows in the table body
    const filas = document.querySelectorAll("#tabla-libros tbody tr");

    // Loop through each row and show/hide based on the filter
    filas.forEach(fila => {
      const titulo = fila.dataset.titulo;
      const autor = fila.dataset.autor;
      const isbn = fila.dataset.isbn;
      const categoria = fila.dataset.categoria;

      const coincide = titulo.includes(filtro) || autor.includes(filtro) || isbn.includes(filtro) || categoria.includes(filtro);
      fila.style.display = coincide ? "" : "none";
    });
  });
});
