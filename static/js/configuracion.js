console.log("configuracion.js cargado");

// Wait until the DOM is fully loaded
document.addEventListener("DOMContentLoaded", () => {
  // Get the container where the dynamic form will be inserted
  const panelContainer = document.getElementById("panel-container");

  // Function to show a form based on the selected section
  function mostrarFormulario(seccion) {
    let formularioHTML = "";

    // If the section is "reportes", build the report form
    if (seccion === "reportes") {
      formularioHTML = `
        <div class="container mt-4">
          <h2 class="text-center mb-4">Agregar Reporte</h2>
          <form id="form-agregar-reporte" class="mx-auto" style="max-width: 500px;">
            <div class="mb-3">
              <label for="tituloReporte" class="form-label">Título del reporte</label>
              <input type="text" class="form-control" id="tituloReporte" required>
            </div>
            <div class="mb-3">
              <label for="descripcionReporte" class="form-label">Descripción</label>
              <textarea class="form-control" id="descripcionReporte" rows="3" required></textarea>
            </div>
            <div class="d-grid">
              <button type="submit" class="btn btn-success">Guardar</button>
              <button type="button" id="btn-cancelar" class="btn btn-secondary mt-2">Cancelar</button>
            </div>
          </form>
        </div>
      `;
    }
    // If the section is "reservas", build the reservation form
    else if (seccion === "reservas") {
      formularioHTML = `
        <div class="container mt-4">
          <h2 class="text-center mb-4">Hacer Reserva</h2>
          <form id="form-reserva" class="mx-auto" style="max-width: 500px;">
            <div class="mb-3">
              <label for="nombreReserva" class="form-label">Nombre Completo</label>
              <input type="text" class="form-control" id="nombreReserva" required>
            </div>
            <div class="mb-3">
              <label for="correoReserva" class="form-label">Correo Electrónico</label>
              <input type="email" class="form-control" id="correoReserva" required>
            </div>
            <div class="mb-3">
              <label for="libroReserva" class="form-label">Libro a Reservar</label>
              <select class="form-select" id="libroReserva" required>
                <option value="" selected disabled>Seleccione un libro</option>
                <option value="Cien años de soledad">Cien años de soledad</option>
                <option value="Don Quijote de la Mancha">Don Quijote de la Mancha</option>
                <option value="La sombra del viento">La sombra del viento</option>
                <option value="El principito">El principito</option>
              </select>
            </div>
            <div class="row mb-3">
              <div class="col">
                <label for="fechaReserva" class="form-label">Fecha de Reserva</label>
                <input type="date" class="form-control" id="fechaReserva" required>
              </div>
              <div class="col">
                <label for="horaReserva" class="form-label">Hora de Reserva</label>
                <input type="time" class="form-control" id="horaReserva" required>
              </div>
            </div>
            <div class="d-grid">
              <button type="submit" class="btn btn-success">Reservar</button>
              <button type="button" id="btn-cancelar" class="btn btn-secondary mt-2">Cancelar</button>
            </div>
          </form>
        </div>
      `;
    }
    // If the section is "prestamos", build the loan form
    else if (seccion === "prestamos") {
      formularioHTML = `
        <div class="container mt-4">
          <h2 class="text-center mb-4">Registrar Préstamo</h2>
          <form id="form-prestamo" class="mx-auto" style="max-width: 500px;">
            <div class="mb-3">
              <label for="nombrePrestamo" class="form-label">Nombre Completo</label>
              <input type="text" class="form-control" id="nombrePrestamo" required>
            </div>
            <div class="mb-3">
              <label for="correoPrestamo" class="form-label">Correo Electrónico</label>
              <input type="email" class="form-control" id="correoPrestamo" required>
            </div>
            <div class="mb-3">
              <label for="libroPrestamo" class="form-label">Libro a Prestar</label>
              <select class="form-select" id="libroPrestamo" required>
                <option value="" selected disabled>Seleccione un libro</option>
                <option value="Cien años de soledad">Cien años de soledad</option>
                <option value="Don Quijote de la Mancha">Don Quijote de la Mancha</option>
                <option value="La sombra del viento">La sombra del viento</option>
                <option value="El principito">El principito</option>
              </select>
            </div>
            <div class="mb-3">
              <label for="fechaPrestamo" class="form-label">Fecha de Préstamo</label>
              <input type="date" class="form-control" id="fechaPrestamo" required>
            </div>
            <div class="mb-3">
              <label for="fechaDevolucion" class="form-label">Fecha de Devolución</label>
              <input type="date" class="form-control" id="fechaDevolucion" required>
            </div>
            <div class="d-grid">
              <button type="submit" class="btn btn-success">Registrar</button>
              <button type="button" id="btn-cancelar" class="btn btn-secondary mt-2">Cancelar</button>
            </div>
          </form>
        </div>
      `;
    }

    // Insert the built HTML into the container
    panelContainer.innerHTML = formularioHTML;

    // Add a click event to the cancel button to reset the panel
    if (document.getElementById("btn-cancelar")) {
      document.getElementById("btn-cancelar").addEventListener("click", () => {
        panelContainer.innerHTML = `
          <div class="usuario-panel">
            <h4 class="text-white">Panel de opciones</h4>
            <p class="text-secondary">Selecciona una opción para agregar.</p>
          </div>
        `;
      });
    }

    // Add submit handler for the dynamic form
    const form = panelContainer.querySelector("form");
    if (form) {
      form.addEventListener("submit", (e) => {
        e.preventDefault(); // Prevent normal form submission

        let url = "";
        let datos = {};

        // Build data based on the section
        if (seccion === "reportes") {
          url = "/admin/reportes/guardar";
          datos = {
            titulo: document.getElementById("tituloReporte").value,
            descripcion: document.getElementById("descripcionReporte").value,
          };
        } else if (seccion === "reservas") {
          url = "/admin/reservas/guardar";
          datos = {
            nombre: document.getElementById("nombreReserva").value,
            correo: document.getElementById("correoReserva").value,
            libro: document.getElementById("libroReserva").value,
            fecha: document.getElementById("fechaReserva").value,
            hora: document.getElementById("horaReserva").value,
          };
        } else if (seccion === "prestamos") {
          url = "/admin/prestamos/guardar";
          datos = {
            nombre: document.getElementById("nombrePrestamo").value,
            correo: document.getElementById("correoPrestamo").value,
            libro: document.getElementById("libroPrestamo").value,
            fecha_prestamo: document.getElementById("fechaPrestamo").value,
            fecha_devolucion: document.getElementById("fechaDevolucion").value,
          };
        }

        // Send the data using fetch as JSON
        fetch(url, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(datos),
        })
          .then((response) => response.json())
          .then((data) => {
            alert(data.mensaje); // Show the server response
            form.reset(); // Clear the form
          })
          .catch((error) => {
            console.error("Error al enviar el formulario:", error);
          });
      });
    }
  }

  // Get the buttons for adding each section
  const btnAgregarReportes = document.getElementById("btn-agregar-reportes");
  const btnAgregarReservas = document.getElementById("btn-agregar-reservas");
  const btnAgregarPrestamos = document.getElementById("btn-agregar-prestamos");

  // Attach click events to show the corresponding form
  if (btnAgregarReportes) {
    btnAgregarReportes.addEventListener("click", () => mostrarFormulario("reportes"));
  }
  if (btnAgregarReservas) {
    btnAgregarReservas.addEventListener("click", () => mostrarFormulario("reservas"));
  }
  if (btnAgregarPrestamos) {
    btnAgregarPrestamos.addEventListener("click", () => mostrarFormulario("prestamos"));
  }
});
