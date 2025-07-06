// Async function to fetch and update total counts on the dashboard
async function actualizarTotales() {
  try {
    // Make a request to the server to get the latest totals
    const res = await fetch('/api/dashboard_data');
    const data = await res.json();

    // Update the HTML elements with the fetched totals, or 0 if missing
    document.getElementById('total-administradores').innerText = data.total_administradores ?? 0;
    document.getElementById('total-lectores').innerText = data.total_lectores ?? 0;
    document.getElementById('total-libros').innerText = data.total_libros ?? 0;
    document.getElementById('total-prestamos').innerText = data.total_prestamos ?? 0;
    document.getElementById('total-reservas').innerText = data.total_reservas ?? 0;
    document.getElementById('total-reportes').innerText = data.total_reportes ?? 0;

  } catch (error) {
    // Log any error that occurs during the fetch or update
    console.error('Error al actualizar totales:', error);
  }
}

// Run when the page has loaded
document.addEventListener("DOMContentLoaded", () => {
  // Call the function immediately
  actualizarTotales();

  // Refresh totals every 30 seconds automatically
  setInterval(actualizarTotales, 30000);

  // 📊 Chart: Most loaned books
  fetch('/api/libros_populares')
    .then(res => res.json())
    .then(data => {
      // Get the canvas context for the chart
      const ctx = document.getElementById('graficoLibrosPopulares').getContext('2d');

      // Create a new bar chart with the popular books data
      new Chart(ctx, {
        type: 'bar',
        data: {
          labels: data.map(d => d.titulo), // Book titles
          datasets: [{
            label: 'Veces prestado',
            data: data.map(d => d.total), // Times loaned
            backgroundColor: '#1cc88a' // Green bar color
          }]
        },
        options: {
          responsive: true,
          plugins: { legend: { display: false } } // Hide the legend
        }
      });
    });

  // 📊 Chart: Books with most delays
  fetch('/api/libros_atrasados')
    .then(res => res.json())
    .then(data => {
      // Get the canvas context for the chart
      const ctx = document.getElementById('graficoLibrosAtrasados').getContext('2d');

      // Create a new bar chart with the overdue books data
      new Chart(ctx, {
        type: 'bar',
        data: {
          labels: data.map(d => d.titulo), // Book titles
          datasets: [{
            label: 'Veces atrasado',
            data: data.map(d => d.total), // Times overdue
            backgroundColor: '#e74a3b' // Red bar color
          }]
        },
        options: {
          responsive: true,
          plugins: { legend: { display: false } } // Hide the legend
        }
      });
    });
});
