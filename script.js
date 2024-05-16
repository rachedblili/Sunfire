const form = document.getElementById('video-form');
const imageInput = document.getElementById('image-input');
const imageShelf = document.getElementById('image-shelf');
const imageContainers = imageShelf.querySelectorAll('.image-container');
const generateBtn = document.getElementById('generate-btn');
const videoContainer = document.getElementById('video-container');
const generatedVideo = document.getElementById('generated-video');

// Add event listener for file input
imageInput.addEventListener('change', previewImages);

// Preview selected images
function previewImages() {
  const files = this.files;

  if (files.length > 5) {
    alert('You can only select up to 5 images.');
    this.value = '';
    return;
  }

  for (let i = 0; i < files.length; i++) {
    const file = files[i];
    const reader = new FileReader();

    reader.onload = function () {
      const img = imageContainers[i].querySelector('.image-preview');
      img.file = file;
      img.src = reader.result;
      imageContainers[i].querySelector('.move-left').disabled = i === 0;
      imageContainers[i].querySelector('.move-right').disabled = i === files.length - 1;
    }

    reader.readAsDataURL(file);
  }

  // Clear remaining image containers
  for (let i = files.length; i < imageContainers.length; i++) {
    const img = imageContainers[i].querySelector('.image-preview');
    img.src = '';
    img.file = null;
  }
}

// Move image left or right
imageShelf.addEventListener('click', (e) => {
  if (e.target.classList.contains('move-left')) {
    moveImageLeft(e.target.parentElement);
  } else if (e.target.classList.contains('move-right')) {
    moveImageRight(e.target.parentElement);
  }
});

function moveImageLeft(container) {
  const index = Array.from(imageContainers).indexOf(container);
  if (index > 0) {
    const prevContainer = imageContainers[index - 1];
    const tempSrc = container.querySelector('.image-preview').src;
    const tempFile = container.querySelector('.image-preview').file;
    container.querySelector('.image-preview').src = prevContainer.querySelector('.image-preview').src;
    container.querySelector('.image-preview').file = prevContainer.querySelector('.image-preview').file;
    prevContainer.querySelector('.image-preview').src = tempSrc;
    prevContainer.querySelector('.image-preview').file = tempFile;
    updateButtonStates();
  }
}

function moveImageRight(container) {
  const index = Array.from(imageContainers).indexOf(container);
  if (index < imageContainers.length - 1) {
    const nextContainer = imageContainers[index + 1];
    const tempSrc = container.querySelector('.image-preview').src;
    const tempFile = container.querySelector('.image-preview').file;
    container.querySelector('.image-preview').src = nextContainer.querySelector('.image-preview').src;
    container.querySelector('.image-preview').file = nextContainer.querySelector('.image-preview').file;
    nextContainer.querySelector('.image-preview').src = tempSrc;
    nextContainer.querySelector('.image-preview').file = tempFile;
    updateButtonStates();
  }
}

function updateButtonStates() {
  imageContainers.forEach((container, index) => {
    const moveLeft = container.querySelector('.move-left');
    const moveRight = container.querySelector('.move-right');
    moveLeft.disabled = index === 0;
    moveRight.disabled = index === imageContainers.length - 1 || container.querySelector('.image-preview').src === '';
  });
}

// Handle form submission
form.addEventListener('submit', function (e) {
  e.preventDefault();

  const formData = new FormData(form);
//  const data = {};
//
//  for (const [key, value] of formData.entries()) {
//    if (key === 'image-input') {
//      data[key] = [...value];
//    } else {
//      data[key] = value;
//    }
//  }
//
//  // Get image sources in the correct order
//  const imageSources = Array.from(imageContainers)
//    .filter(container => container.querySelector('.image-preview').src !== '')
//    .map(container => container.querySelector('.image-preview').src);
//  data.images = imageSources;
  // First, remove the existing file entries from formData if they exist
  formData.delete('images');

  // Get image sources in the correct order and append them to formData
  const imageFiles = Array.from(imageContainers)
    .filter(container => container.querySelector('.image-preview').src !== '')
    .map(container => container.querySelector('.image-preview').file); 

  // Append each image file to formData
  imageFiles.forEach(file => {
    if (file) {
      formData.append('images', file);
    }
  });

  // Send data to Flask backend
  fetch('/api/generate-video', {
    method: 'POST',
    body: formData 
  })
	.then(response => response.json())
    	.then(responseData => {
      	  generatedVideo.src = responseData.video_url;
          videoContainer.style.display = 'block';
    	})
    	.catch(error => {
      	  console.error('Error:', error);
      	  alert('An error occurred while generating the video.');
    	});
});