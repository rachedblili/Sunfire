const form = document.getElementById('video-form');
const imageInput = document.getElementById('image-input');
const imageShelf = document.getElementById('image-shelf');
const imageContainers = imageShelf.querySelectorAll('.image-container');
const generateBtn = document.getElementById('generate-btn');
const videoContainer = document.getElementById('video-container');
const generatedVideo = document.getElementById('generated-video');

// ... (existing code for image preview and reordering) ...

// Handle form submission
form.addEventListener('submit', function (e) {
  e.preventDefault();

  const formData = new FormData(form);

  fetch('/generate-video', {
    method: 'POST',
    body: formData
  })
    .then(response => response.json())
    .then(data => {
      generatedVideo.src = data.video_url;
      videoContainer.style.display = 'block';
    })
    .catch(error => {
      console.error('Error:', error);
      alert('An error occurred while generating the video.');
    });
});
