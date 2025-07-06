// Declare variables to store the current mode (edit or delete) and the selected user
let modo = null;
let usuarioSeleccionado = null;

// Wait until the DOM is fully loaded
document.addEventListener("DOMContentLoaded", () => {
  // Get the Edit and Delete buttons by their IDs
  const editarBtn = document.getElementById("btn-editar");
  const eliminarBtn = document.getElementById("btn-eliminar");
  const tabla = document.getElementById("tabla-usuarios");

  // If the Edit button exists, add a click event to activate edit mode
  if (editarBtn) {
    editarBtn.addEventListener("click", () => {
      modo = "editar";
      activarSeleccion();
    });
  }

  // If the Delete button exists, add a click event to activate delete mode
  if (eliminarBtn) {
    eliminarBtn.addEventListener("click", () => {
      modo = "eliminar";
      activarSeleccion();
    });
  }

  // Function to activate row selection in the table
  function activarSeleccion() {
    // Add a click event listener to each table row in the tbody
    document.querySelectorAll("#tabla-usuarios tbody tr").forEach(fila => {
      fila.addEventListener("click", () => {
        // When a row is clicked, store the user data from data attributes
        usuarioSeleccionado = {
          id: fila.dataset.id,
          nombre: fila.dataset.nombre,
          email: fila.dataset.email,
          rol: fila.dataset.rol
        };
        // Open the modal and fill it with user data
        abrirModal(usuarioSeleccionado);
      });
    });
  }

  // Function to open the modal with the user information
  function abrirModal(usuario) {
    // Fill the modal input fields with the selected user's data
    document.getElementById("usuario-id").value = usuario.id;
    document.getElementById("usuario-nombre").value = usuario.nombre;
    document.getElementById("usuario-email").value = usuario.email;
    document.getElementById("usuario-rol").value = usuario.rol;

    // Show or hide buttons and alert based on mode
    document.getElementById("btn-confirmar-eliminar").classList.toggle("d-none", modo !== "eliminar");
    document.getElementById("btn-guardar").classList.toggle("d-none", modo !== "editar");
    document.getElementById("alerta-eliminar").classList.toggle("d-none", modo !== "eliminar");

    // Show the Bootstrap modal
    new bootstrap.Modal(document.getElementById("modalUsuario")).show();
  }

  // Handle the form submission for editing
  document.getElementById("formUsuario").addEventListener("submit", function (e) {
    e.preventDefault();
    if (modo === "editar") {
      // Collect form data
      const datos = {
        id: document.getElementById("usuario-id").value,
        nombre: document.getElementById("usuario-nombre").value,
        email: document.getElementById("usuario-email").value,
        rol: document.getElementById("usuario-rol").value
      };
      // Send a POST request to edit the user and reload the page when done
      fetch("/admin/usuarios/editar", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(datos)
      }).then(() => location.reload());
    }
  });

  // Handle the confirmation click for deleting a user
  document.getElementById("btn-confirmar-eliminar").addEventListener("click", function () {
    // Send a POST request to delete the selected user and reload the page when done
    fetch(`/admin/usuarios/eliminar/${usuarioSeleccionado.id}`, {
      method: "POST"
    }).then(() => location.reload());
  });
});
