const form = document.getElementById('video-form');
const imageInput = document.getElementById('image-input');
const imageShelf = document.getElementById('image-shelf');
const imageContainers = imageShelf.querySelectorAll('.image-container');
const generateBtn = document.getElementById('generate-btn');
const videoContainer = document.getElementById('video-container');
const logContainer = document.getElementById('log-container');
const generatedVideo = document.getElementById('generated-video');
const videoPopup = document.getElementById('video-popup');
const closePopup = document.getElementById('close-popup');
const testPopupBtn = document.getElementById('test-popup-btn');

function clearContainers() {
        if (logContainer) {
            logContainer.innerHTML = '';
        }
        if (videoContainer && generatedVideo) {
            videoContainer.style.display = 'none';
            generatedVideo.src = '';
        }
}
// Function to show the popup
function showPopup() {
    videoPopup.style.display = 'flex';
}

// Function to hide the popup
function hidePopup() {
    videoPopup.style.display = 'none';
}
var eventSource; // Global event source

function setupEventSource(sessionId) {
    if (eventSource) {
        eventSource.close(); // Close existing connection if it exists
    }
    eventSource = new EventSource("/api/messages?session_id=${sessionId}");

    eventSource.onmessage = function(event) {
        console.log('Received message:', event.data);
        var messageParts = event.data.split(" : ");
        if (messageParts.length === 3) {
            var receivedSessionId = messageParts[0];
            var facility = messageParts[1];
            var message = messageParts[2];
            if (receivedSessionId === sessionId) { // Check if the message is for the correct session
                if (facility === "log") {
                    if (logContainer) {
                        var messageElement = document.createElement('p');
                        messageElement.textContent = message;
                        logContainer.appendChild(messageElement);
                        logContainer.scrollTop = logContainer.scrollHeight;
                    } else {
                        console.error("log-container not found");
                    }
                    } else if (facility === "video") {
                        if (generatedVideo) {
                            generatedVideo.src = message;
                            showPopup();
                            generatedVideo.load();
                            generatedVideo.play().then(() => {
                                console.log('Video started playing');
                            }).catch((error) => {
                                console.error('Error playing video:', error);
                            });
                        } else {
                            console.error("generated-video not found");
                        }
                    }
            }
        }
    };

    eventSource.onerror = function() {
        console.log('EventSource failed.');
    };
}

document.addEventListener("DOMContentLoaded", function() {
    //console.log('DOMContentLoaded event fired');
    //console.log('videoContainer:', videoContainer);
    //console.log('logContainer:', logContainer);
    //console.log('generatedVideo:', generatedVideo);


    const platformSelect = document.getElementById('platform-select');

    clearContainers();

    // Event listener to close the popup
    closePopup.addEventListener('click', hidePopup);

    // Event listener for the test button
    testPopupBtn.addEventListener('click', () => {
        showPopup();
    });

    // Function to set the aspect ratio of the popup based on the selected platform
    function setAspectRatio(platform) {
        const popupContent = document.querySelector('.popup-content');

        let aspectRatio;
        switch (platform) {
            case 'youtube':
            case 'facebook':
            case 'twitter':
            case 'television':
                aspectRatio = { width: 16, height: 9 };
                break;
            case 'instagram':
            case 'tiktok':
                aspectRatio = { width: 9, height: 16 };
                break;
            case 'square':
                aspectRatio = { width: 1, height: 1}
            default:
                aspectRatio = { width: 16, height: 9 };
       }

       const containerWidth = 80; // Default width percentage
       const containerHeight = aspectRatio.width > aspectRatio.height
            ? containerWidth * (aspectRatio.height / aspectRatio.width)
            : containerWidth * 1.5; // Constrain height for vertical aspect ratios

       popupContent.style.width = `${containerWidth}%`;
       popupContent.style.height = `${containerHeight}vw`; // Use vw to scale height relative to viewport width
       popupContent.style.maxWidth = '700px';
       popupContent.style.maxHeight = '90vh'; // Ensure it doesn't exceed viewport height
       popupContent.style.aspectRatio = `${aspectRatio.width} / ${aspectRatio.height}`;
    }

    // Event listener for platform selection change
    platformSelect.addEventListener('change', (event) => {
        setAspectRatio(event.target.value);
    });

    let tonesData;

    fetch('/api/get_tones_data')
        .then(response => {
            return response.json();
        })
        .then(data => {
            tonesData = data;
            console.log("Received tonesData:", tonesData);  // Check the structure
            const toneSelect = document.getElementById('tone-select');
            toneSelect.innerHTML = '<option value="" disabled selected>Select One</option>' +
                Object.keys(tonesData).map(tone =>
                    `<option value="${tone}">${tone}</option>`
                ).join('');
        })
        .catch(error => {
            console.error('Error fetching tones data:', error);
        });

    document.getElementById('tone-select').addEventListener('change', function() {
        const selectedTone = this.value;
        console.log("Selected tone:", selectedTone);
        const ageGenderOptions = tonesData[selectedTone]['age_gender']; // Directly use 'age_gender' from the new data structure
        console.log("Age/Gender options for selected tone:", ageGenderOptions);
        const ageGenderSelect = document.getElementById('age-gender-select');
        ageGenderSelect.innerHTML = '<option value="" disabled selected>Select One</option>' +
            ageGenderOptions.map(option =>
                `<option value="${option}">${option}</option>`
            ).join('');
        ageGenderSelect.style.visibility = 'visible';
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
    moveImageLeft(e.target.closest('.image-container')); // Adjusted to find the closest .image-container
  } else if (e.target.classList.contains('move-right')) {
    moveImageRight(e.target.closest('.image-container')); // Adjusted to find the closest .image-container
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
	    //console.log('Response:',response)
        if (response.ok) {
            return response.json();
        } else {
            throw new Error('Failed to initiate video generation process.');
        }
    })
    .then(data => {
        const sessionId = data.session_id; // Capture the session_id
        setupEventSource(sessionId); // Pass the session_id to the setupEventSource function
    })
    .catch(error => {
        console.error('Error:', error);
        alert('An error occurred while generating the video.');
    });
});
