// Execute when the DOM is fully loaded
document.addEventListener("DOMContentLoaded", function () {
  // Get modal element, body, title, and create Bootstrap instance
  const modalElement = document.getElementById("modalReserva");
  const modalBody = document.getElementById("modal-reserva-body");
  const modalTitle = document.getElementById("modalReservaLabel");
  const modalInstance = modalElement ? new bootstrap.Modal(modalElement) : null;

  // Helper: Apply a fade/slide animation to an element
  const aplicarAnimacion = (elemento) => {
    elemento.style.opacity = 0;
    elemento.style.transform = "translateY(40px)";
    elemento.style.transition = "opacity 0.2s ease, transform 0.2s ease";
    setTimeout(() => {
      elemento.style.opacity = 1;
      elemento.style.transform = "translateY(0)";
    }, 10);
  };

  // Helper: Show a loading spinner in a container
  const mostrarCargando = (contenedor) => {
    contenedor.innerHTML = `
      <div class="d-flex justify-content-center align-items-center p-4">
        <div class="spinner-border text-primary" role="status">
          <span class="visually-hidden">Cargando...</span>
        </div>
      </div>
    `;
  };

  // 📄 Show list of reservations
  document.getElementById("btn-mostrar-reservas")?.addEventListener("click", () => {
    if (!modalInstance) return;
    modalTitle.textContent = "Lista de Reservas";
    mostrarCargando(modalBody);

    fetch('/admin/reservas/mostrar')
      .then(response => response.text())
      .then(html => {
        modalBody.innerHTML = html;
        aplicarAnimacion(modalBody);
        modalInstance.show();
      });
  });

  // ➕ Show form to add a new reservation
  document.getElementById("btn-agregar-reservas")?.addEventListener("click", () => {
    if (!modalInstance) return;
    modalTitle.textContent = "Agregar Reserva";
    mostrarCargando(modalBody);

    fetch("/admin/reservas/nuevo")
      .then(response => response.text())
      .then(html => {
        modalBody.innerHTML = html;
        aplicarAnimacion(modalBody);
        modalInstance.show();

        // Initialize form logic after load
        setTimeout(inicializarFormularioReserva, 100);
      });
  });

  // 📝 Delegated event: Edit reservation
  document.addEventListener("click", function (e) {
    const editarBtn = e.target.closest(".btn-editar-reserva");
    if (editarBtn && modalInstance) {
      const id = editarBtn.getAttribute("data-id");
      modalTitle.textContent = "Editar Reserva";
      mostrarCargando(modalBody);

      fetch(`/admin/reservas/editar_formulario/${id}`)
        .then(res => res.text())
        .then(html => {
          modalBody.innerHTML = html;
          aplicarAnimacion(modalBody);
          modalInstance.show();
        });
    }
  });

  // ❌ Delegated event: Delete reservation
  document.addEventListener("click", function (e) {
    const eliminarBtn = e.target.closest(".btn-eliminar-reserva");
    if (eliminarBtn) {
      const id = eliminarBtn.dataset.id;
      if (confirm("¿Estás seguro de eliminar esta reserva?")) {
        fetch(`/admin/reservas/eliminar/${id}`, {
          method: "POST"
        })
          .then(resp => resp.json())
          .then(data => {
            alert(data.mensaje || "Reserva eliminada");
            eliminarBtn.closest("tr").remove();
          })
          .catch(err => {
            console.error("Error al eliminar reserva:", err);
            alert("Error al eliminar reserva.");
          });
      }
    }
  });

  // 🔙 Delegated event: Cancel reservation modal
  document.addEventListener("click", function (e) {
    const cancelarBtn = e.target.closest(".btn-cancelar-reserva");
    if (cancelarBtn && modalInstance) {
      modalInstance.hide();
    }
  });

  // 🗂️ Initialize reservation form and handle submit
  function inicializarFormularioReserva() {
    const form = document.getElementById("form-reserva");
    if (!form) return;

    form.addEventListener("submit", function (e) {
      e.preventDefault();
      const datos = {
        usuario_id: document.getElementById("usuario_id").value,
        libro_id: document.getElementById("libro_id").value,
        fecha_reserva: document.getElementById("fecha_reserva").value
      };

      fetch("/admin/reservas/guardar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(datos)
      })
        .then((res) => res.json())
        .then((respuesta) => {
          if (respuesta.mensaje) {
            alert(respuesta.mensaje);
            form.reset();
          }
        })
        .catch((err) => {
          console.error("Error al guardar reserva:", err);
          alert("Error al guardar la reserva.");
        });
    });
  }
});
