const form = document.getElementById('video-form');
const imageInput = document.getElementById('image-input');
const imageShelf = document.getElementById('image-shelf');
const imageContainers = imageShelf.querySelectorAll('.image-container');
const generateBtn = document.getElementById('generate-btn');
const videoContainer = document.getElementById('video-container');
const logContainer = document.getElementById('log-container');
const generatedVideo = document.getElementById('generated-video');

function clearContainers() {
        if (logContainer) {
            logContainer.innerHTML = '';
        }
        if (videoContainer && generatedVideo) {
            videoContainer.style.display = 'none';
            generatedVideo.src = '';
        }
}

document.addEventListener("DOMContentLoaded", function() {
    console.log('DOMContentLoaded event fired');
    console.log('videoContainer:', videoContainer);
    console.log('logContainer:', logContainer);
    console.log('generatedVideo:', generatedVideo);

    clearContainers();
    var eventSource = new EventSource("/api/messages");
    let tonesData;

    fetch('/api/get_tones_data')
        .then(response => response.json())
        .then(data => {
            tonesData = data;
            const toneSelect = document.getElementById('tone-select');
            toneSelect.innerHTML = Object.keys(tonesData).map(tone =>
                `<option value="${tone}">${tone.charAt(0).toUpperCase() + tone.slice(1)}</option>`
            ).join('');
        });

    document.getElementById('tone-select').addEventListener('change', function() {
        const selectedTone = this.value.toLowerCase(); // Ensure selected tone is in lowercase
        const ageGenderOptions = getAgeGenderCombinations(tonesData[selectedTone]);
        const ageGenderSelect = document.getElementById('age-gender-select');
        ageGenderSelect.innerHTML = ageGenderOptions.map(option =>
            `<option value="${option}">${option}</option>`
        ).join('');
        ageGenderSelect.style.display = 'inline-block';
    });

    document.getElementById('age-gender-select').addEventListener('change', function() {
        const toneSelect = document.getElementById('tone-select').value.toLowerCase();
        const ageGenderSelect = this.value;
        const formInput = document.createElement('input');
        formInput.type = 'hidden';
        formInput.name = 'tone_age_gender';
        formInput.value = `${toneSelect}:${ageGenderSelect}`;
        document.querySelector('form').appendChild(formInput);
    });

    function getAgeGenderCombinations(voices) {
        const combinations = new Set();
        voices.forEach(voice => {
            if (voice.age && voice.gender) { // Check for non-empty age and gender
                const combination = `${voice.age} ${voice.gender}`;
                combinations.add(combination);
            }
        });
        return Array.from(combinations).sort();
    }

    eventSource.onmessage = function(event) {
        console.log('Received message:', event.data);
        var messageParts = event.data.split(" : ");
        if (messageParts.length === 2) {
            var facility = messageParts[0];
            var message = messageParts[1];

            if (facility === "log") {
                console.log('Handling log message:', message);
                if (logContainer) {
                    var messageElement = document.createElement('p');
                    messageElement.textContent = message;
                    logContainer.appendChild(messageElement);
                } else {
                    console.error("log-container not found");
                }
            } else if (facility === "video") {
                console.log('Handling video message:', message);
                if (videoContainer && generatedVideo) {
                    generatedVideo.src = message;
                    videoContainer.style.display = 'block';
                    generatedVideo.load();
                    generatedVideo.play().then(() => {
                        console.log('Video started playing');
                    }).catch((error) => {
                        console.error('Error playing video:', error);
                    });
                } else {
                    console.error("video-container or generated-video not found");
                }
            }
        }
    };

    eventSource.onerror = function() {
        console.log('EventSource failed.');
    };
});

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
  clearContainers();
  const formData = new FormData(form);

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
	.then(response => {
	    console.log('Response:',response)
        if (response.ok) {
            return response.json();
        } else {
            throw new Error('Failed to initiate video generation process.');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('An error occurred while generating the video.');
    });
});
