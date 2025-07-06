// Function to load page content inside an iframe by setting its src
function loadContent(pagina) {
  document.getElementById('main-content').src = `/admin/${pagina}`;
}

// Function to toggle submenu visibility
function toggleSubmenu(e, link) {
  e.preventDefault(); // Prevent default link behavior
  const menuItem = link.closest('.menu-item');

  // If the menu item is already open, close it
  if (menuItem.classList.contains('open')) {
    menuItem.classList.remove('open');
  } else {
    // Otherwise, close all other open menu items
    document.querySelectorAll('.menu-item.open').forEach(item => {
      item.classList.remove('open');
    });
    // Open the clicked menu item
    menuItem.classList.add('open');
  }
}

// Wait for the DOM to be fully loaded
document.addEventListener("DOMContentLoaded", () => {
  // Get all menu and submenu links
  const links = document.querySelectorAll(".menu-link, .submenu-link");
  const toggleBtn = document.getElementById('sidebarToggle');
  const sidebar = document.getElementById('sidebar');
  const toggleIcon = toggleBtn.querySelector(".toggle-icon");

  // Handle link clicks to mark active link
  links.forEach((link) => {
    link.addEventListener("click", () => {
      // Do not mark as active if it is a parent menu with a submenu
      if (link.classList.contains('has-submenu')) return;

      // Remove active class from all links and add it to the clicked one
      links.forEach((l) => l.classList.remove("active"));
      link.classList.add("active");
    });
  });

  // Sidebar toggle button logic
  toggleBtn.addEventListener("click", () => {
    // Toggle collapsed class on sidebar
    sidebar.classList.toggle("collapsed");
    // Rotate toggle icon if sidebar is collapsed
    toggleIcon.style.transform = sidebar.classList.contains("collapsed") ? "rotate(180deg)" : "rotate(0deg)";
  });

  // Chart: Most borrowed books
  fetch('/api/libros_populares')
    .then(res => res.json())
    .then(data => {
      // Get chart context if element exists
      const ctx = document.getElementById('graficoLibrosPopulares')?.getContext('2d');
      if (ctx) {
        // Create a bar chart
        new Chart(ctx, {
          type: 'bar',
          data: {
            labels: data.map(d => d.titulo),
            datasets: [{
              label: 'Veces prestado',
              data: data.map(d => d.total),
              backgroundColor: '#1cc88a'
            }]
          },
          options: {
            responsive: true,
            plugins: { legend: { display: false } }
          }
        });
      }
    });

  // Chart: Books with most delays
  fetch('/api/libros_atrasados')
    .then(res => res.json())
    .then(data => {
      // Get chart context if element exists
      const ctx = document.getElementById('graficoLibrosAtrasados')?.getContext('2d');
      if (ctx) {
        // Create a bar chart
        new Chart(ctx, {
          type: 'bar',
          data: {
            labels: data.map(d => d.titulo),
            datasets: [{
              label: 'Veces atrasado',
              data: data.map(d => d.total),
              backgroundColor: '#e74a3b'
            }]
          },
          options: {
            responsive: true,
            plugins: { legend: { display: false } }
          }
        });
      }
    });
});
