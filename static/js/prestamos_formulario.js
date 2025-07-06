// Add submit event listener to the form with id "form-prestamo"
document.getElementById("form-prestamo").addEventListener("submit", function (e) {
  e.preventDefault(); // Prevent default form submission behavior

  // Gather form data into an object
  const datos = {
    usuario_id: document.getElementById("usuario_id").value,
    libro_id: document.getElementById("libro_id").value,
    fecha_prestamo: document.getElementById("fecha_prestamo").value
  };

  // Send the data to the backend using fetch with POST method
  fetch("/admin/prestamos/guardar", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(datos)
  })
    .then(res => res.json()) // Parse response as JSON
    .then(respuesta => {
      if (respuesta.mensaje) {
        // If a message is received, show the notification element
        document.getElementById("notificacion-prestamo").classList.remove("d-none");
        // Optionally reset the form fields
        document.getElementById("form-prestamo").reset();
      }
    });
});
