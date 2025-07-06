// Execute when the DOM is fully loaded
document.addEventListener("DOMContentLoaded", function () {
  // Modal elements
  const modalElement = document.getElementById("modalPrestamo");
  const modalBody = document.getElementById("modal-prestamo-body");
  const modalTitle = document.getElementById("modalPrestamoLabel");
  const contenido = document.getElementById("contenido-opcion");

  // Function to apply smooth animation when showing content
  const aplicarAnimacion = (elemento) => {
    elemento.style.opacity = 0;
    elemento.style.transform = "translateY(40px)";
    elemento.style.transition = "opacity 0.2s ease, transform 0.2s ease";
    setTimeout(() => {
      elemento.style.opacity = 1;
      elemento.style.transform = "translateY(0)";
    }, 10);
  };

  // Function to show a spinner while content is loading
  const mostrarCargando = (contenedor) => {
    contenedor.innerHTML = `
      <div class="d-flex justify-content-center align-items-center p-4">
        <div class="spinner-border text-primary" role="status">
          <span class="visually-hidden">Cargando...</span>
        </div>
      </div>
    `;
  };

  // Function to load dynamic content, either inside the modal or the main container
  const cargarContenido = (url, forzarModal = false) => {
    const mostrarEnModal = url.includes("nuevo") || url.includes("editar") || forzarModal;

    if (mostrarEnModal) {
      // Set modal title based on URL
      modalTitle.textContent = url.includes("nuevo")
        ? "Agregar Préstamo"
        : url.includes("editar")
        ? "Editar Préstamo"
        : "Lista de Préstamos";

      // Show loading spinner in modal body
      mostrarCargando(modalBody);

      // Fetch content from server
      fetch(url)
        .then((response) => response.text())
        .then((html) => {
          modalBody.innerHTML = html;   // Insert fetched HTML
          aplicarAnimacion(modalBody);  // Apply smooth animation
          new bootstrap.Modal(modalElement).show();  // Show modal

          // If new loan form, initialize form logic
          if (url.includes("nuevo")) {
            setTimeout(inicializarFormularioPrestamo, 100);
          }
        });
    } else {
      // Load content in main container instead of modal
      mostrarCargando(contenido);
      fetch(url)
        .then((response) => response.text())
        .then((html) => {
          contenido.innerHTML = html;
          aplicarAnimacion(contenido);
        });
    }
  };

  // Events to load loan list or add new loan
  document.getElementById("btn-mostrar-prestamos")?.addEventListener("click", () => {
    cargarContenido("/admin/prestamos/mostrar", true); // Force load inside modal
  });

  document.getElementById("btn-agregar-prestamos")?.addEventListener("click", () => {
    cargarContenido("/admin/prestamos/nuevo"); // Open new loan form
  });

  // Function to initialize loan form submission logic
  function inicializarFormularioPrestamo() {
    const form = document.getElementById("form-prestamo");
    if (!form) return;

    form.addEventListener("submit", function (e) {
      e.preventDefault(); // Prevent default form submit

      // Gather form data
      const datos = {
        usuario_id: document.getElementById("usuario_id").value,
        libro_id: document.getElementById("libro_id").value,
        fecha_prestamo: document.getElementById("fecha_prestamo").value
      };

      // Send data using fetch to backend
      fetch("/admin/prestamos/guardar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(datos)
      })
        .then((res) => res.json())
        .then((respuesta) => {
          if (respuesta.mensaje) {
            // Show notification if message returned
            document.getElementById("notificacion-prestamo")?.classList.remove("d-none");
            form.reset(); // Reset form fields
          }
        })
        .catch((err) => {
          console.error("Error al guardar préstamo:", err);
          alert("Error al guardar el préstamo.");
        });
    });
  }
});
