// Initialize the slide index
let index = 0;

// Function to move the carousel slide by a given step
function moveSlide(step) {
  // Get the slide container element
  const slideContainer = document.querySelector('.carousel-slide');

  // Get all the images inside the slide container
  const images = slideContainer.querySelectorAll('img');

  // Calculate total number of images
  const total = images.length;

  // Update the index cyclically
  index = (index + step + total) % total;

  // Move the slide container to show the current image
  slideContainer.style.transform = `translateX(-${index * 100}%)`;

  // Add a click event listener to each image (⚠️ Note: this part only works if 'img' is defined)
  img.addEventListener('click', () => {
    // Get the src attribute of the clicked image
    const src = img.getAttribute('src');

    // Log the src for debugging
    console.log("Hiciste clic en:", src); // ✅ this confirms if the image click is captured

    // Save favorites to local storage (⚠️ Note: 'favorites' must be defined somewhere)
    localStorage.setItem("favoriteBooks", JSON.stringify(favorites));
  });
}
