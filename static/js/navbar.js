// static/js/navbar.js
document.addEventListener("DOMContentLoaded", function() {
    // Fetch and include the navigation bar using absolute path
    fetch("/static/js/navbar.html")  // Adjusted path with leading slash
      .then(response => response.text())
      .then(data => {
        // Insert the HTML content into the 'navbar-container' div
        document.getElementById("navbar-container").innerHTML = data;
      })
      .catch(error => console.error("Error loading navigation bar:", error));
  });
  