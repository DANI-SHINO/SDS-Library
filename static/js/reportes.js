// Execute when the DOM is fully loaded
document.addEventListener("DOMContentLoaded", function () {
  // Initialize Bootstrap modal for the report
  const modal = new bootstrap.Modal(document.getElementById("modalReporte"));
  const modalBody = document.getElementById("modal-reporte-body");

  // Function to load report content dynamically
  const cargarReporte = (url) => {
    fetch(url)
      .then(response => response.text()) // Get HTML from server
      .then(html => {
        modalBody.innerHTML = html; // Insert HTML into modal body
        modal.show(); // Show the modal
      })
      .catch(error => {
        // If there is an error, show a message inside the modal body
        modalBody.innerHTML = `<div class="text-danger">Error al cargar el reporte.</div>`;
      });
  };

  // Event listener for "Delayed Books" button
  document.getElementById("btn-libros-atrasados")?.addEventListener("click", () => {
    cargarReporte("/admin/reportes/atrasados");
  });

  // Event listener for "Loaned Books" button
  document.getElementById("btn-libros-prestados")?.addEventListener("click", () => {
    cargarReporte("/admin/reportes/prestados");
  });

  // Event listener for "Popular Books" button
  document.getElementById("btn-libros-populares")?.addEventListener("click", () => {
    cargarReporte("/admin/reportes/populares");
  });
});
