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
const dropArea = document.getElementById('drop-area');
const progressBarContainer = document.getElementById('progressBarContainer');
const progressBar = document.getElementById('progressBar');

function clearContainers() {
        if (logContainer) {
            logContainer.innerHTML = '';
        }
        if (videoContainer && generatedVideo) {
            videoContainer.style.display = 'none';
            generatedVideo.src = '';
        }
}

// Progress Bar Functions
function showProgressBar() {
    progressBarContainer.style.display = 'block';
}
function hideProgressBar() {
    progressBarContainer.style.display = 'none';
}
function fillProgressBar() {
    let currentWidth = parseInt(progressBar.style.width);
    if (isNaN(currentWidth)) currentWidth = 10; // Initial width is 5px
    if (currentWidth < 200) { // Ensure the width does not exceed 200
        currentWidth += 5;
        progressBar.style.width = currentWidth + 'px';
    }
}
function resetProgressBar(){
    progressBar.style.width = '10px';
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
                        fillProgressBar();
                        var messageElement = document.createElement('p');
                        messageElement.textContent = message;
                        logContainer.appendChild(messageElement);
                        logContainer.scrollTop = logContainer.scrollHeight;
                    } else {
                        console.error("log-container not found");
                    }
                } else if (facility == "error") {
                        hideProgressBar();
                        resetProgressBar();
                        var messageElement = document.createElement('p');
                        messageElement.textContent = "ERROR:" + message;
                        logContainer.appendChild(messageElement);
                        logContainer.scrollTop = logContainer.scrollHeight;
                } else if (facility === "video") {
                    hideProgressBar();
                    resetProgressBar();
                    if (generatedVideo) {
                        generatedVideo.src = message;
                        showPopup();
                        let hyperlink = document.createElement('a');
                        hyperlink.href = message;
                        hyperlink.textContent = "Click Here to Download Video - Link Expires in 60 minutes";
                        let paragraph = document.createElement('p');
                        paragraph.appendChild(hyperlink);
                        logContainer.appendChild(paragraph)
                        logContainer.scrollTop = logContainer.scrollHeight;
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
    let imageContainers = [];
    let dragStarted = false;
    let initialContainerCount = 0; // To track the count of containers when drag starts

    dropArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropArea.classList.add('dragging');
    });

    dropArea.addEventListener('dragleave', () => {
        dropArea.classList.remove('dragging');
    });

    dropArea.addEventListener('dragstart', (e) => {
        dragStarted = true; // Set the flag indicating a drag has started
        initialContainerCount = imageContainers.length; // Record the number of containers at drag start
    });

    dropArea.addEventListener('drop', (e) => {
        e.preventDefault();
        dropArea.classList.remove('dragging');
        const files = e.dataTransfer.files;

        if (dragStarted) { // Check if it's a reorder by ensuring no new files are added
          setTimeout(() => {
            if (imageContainers.length > initialContainerCount) {
              console.log('Extra container detected, removing last added container.');
              const extraContainer = imageContainers.pop();
              extraContainer.remove();
              updateImageContainerOrder();
            }
            dragStarted = false; // Reset the flag
          }, 100); // Delay to ensure all DOM updates and JavaScript processing are complete
        } else {
          handleFiles(files);
        }
    });
    dropArea.addEventListener('touchstart', startTouchDrag);
    dropArea.addEventListener('touchmove', dragTouch);
    dropArea.addEventListener('touchend', endTouchDrag);
    dropArea.addEventListener('click', () => {
        imageInput.click();
    });
    dropArea.addEventListener('touchend', () => {
        imageInput.click();
    });

    imageInput.addEventListener('change', () => {
        const files = imageInput.files;
        handleFiles(files);
    });

    function handleFiles(files) {
        if (files.length + imageContainers.length > 6) {
          alert('You can only select up to 6 images.');
          return;
        }

        [...files].forEach(file => {
          const reader = new FileReader();
          reader.onload = () => {
            createImageContainer(reader.result, file);
          };
          reader.readAsDataURL(file);
        });
    }

    function createImageContainer(src, file) {
        const container = document.createElement('div');
        container.classList.add('image-container');
        container.draggable = true;

        const img = document.createElement('img');
        img.classList.add('image-preview');
        img.src = src;
        img.file = file;

        const removeBtn = document.createElement('button');
        removeBtn.classList.add('remove-image');
        removeBtn.textContent = 'x';
        removeBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          imageShelf.removeChild(container);
          imageContainers = imageContainers.filter(c => c !== container);
        });

        container.appendChild(img);
        container.appendChild(removeBtn);
        imageShelf.appendChild(container);
        imageContainers.push(container);

        container.addEventListener('dragstart', () => {
          container.classList.add('dragging');
          //e.stopPropagation();
        });

        container.addEventListener('dragend', () => {
          container.classList.remove('dragging');
          //e.stopPropagation();
          updateImageContainerOrder();
        });

        container.addEventListener('dragover', (e) => {
          e.preventDefault();
          const dragging = document.querySelector('.dragging');
          e.stopPropagation();
          if (dragging && dragging !== container) {
            const rect = container.getBoundingClientRect();
            const offset = e.clientX - rect.left;
            if (offset > rect.width / 2) {
              imageShelf.insertBefore(dragging, container.nextSibling);
            } else {
              imageShelf.insertBefore(dragging, container);
            }
          }
        });

        // Add touch support
        container.addEventListener('touchstart', startTouchDrag);
        container.addEventListener('touchmove', dragTouch);
        container.addEventListener('touchend', endTouchDrag);
    }

    function updateImageContainerOrder() {
        imageContainers = [...imageShelf.children];
    }
    function startTouchDrag(event) {
        const target = event.target;
        if (target.classList.contains('image-container')) {
            target.addEventListener('touchmove', dragTouch);
            target.addEventListener('touchend', endTouchDrag);
            event.preventDefault();
        }
    }

    function dragTouch(event) {
        const target = event.target;
        const touch = event.touches[0];
        target.style.left = `${touch.pageX - target.offsetWidth / 2}px`;
        target.style.top = `${touch.pageY - target.offsetHeight / 2}px`;
        event.preventDefault();
    }

    function endTouchDrag(event) {
        const target = event.target;
        target.removeEventListener('touchmove', dragTouch);
        target.removeEventListener('touchend', endTouchDrag);
        event.preventDefault();
    }
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
                aspectRatio = { width: 1, height: 1};
                break;
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
       // Adjust video dimensions within the popup
        if (generatedVideo) {
            generatedVideo.style.maxWidth = '100%';
            generatedVideo.style.maxHeight = '80vh';
        }
    }

    // Event listener for platform selection change
    platformSelect.addEventListener('change', (event) => {
        setAspectRatio(event.target.value);
    });

});


function pollResult(session_id) {
    const interval = setInterval(function() {
        fetch(`/api/get_video_url/${session_id}`)
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    console.log('Result received:', data.video_url);
                    clearInterval(interval);  // Stop polling
                    hideProgressBar();
                    resetProgressBar();
                    if (generatedVideo) {
                        generatedVideo.src = data.video_url;
                        showPopup();
                        let hyperlink = document.createElement('a');
                        hyperlink.href = message;
                        hyperlink.textContent = "Click Here to Download Video - Link Expires in 60 minutes";
                        let paragraph = document.createElement('p');
                        paragraph.appendChild(hyperlink);
                        logContainer.appendChild(paragraph)
                        logContainer.scrollTop = logContainer.scrollHeight;
                        generatedVideo.load();
                        generatedVideo.play().then(() => {
                            console.log('Video started playing');
                        }).catch((error) => {
                            console.error('Error playing video:', error);
                        });
                    } else {
                        console.error("generated-video not found");
                    }
                } else {
                    console.log('Still waiting for result...');
                }
            })
            .catch(err => {
                console.error('Error fetching result:', err);
            });
    }, 5000);  // Poll every 5 seconds
}



// Handle form submission
form.addEventListener('submit', function (e) {

  const imageCount = imageShelf.querySelectorAll('.image-container').length;

  // Check if there are at least 1 image and no more than 6 images
  if (imageCount === 0) {
    alert('Please attach at least one image before submitting.');
    return; // Prevent form submission
  } else if (imageCount > 6) {
    alert('You cannot attach more than 6 images.');
    return; // Prevent form submission
  }

  e.preventDefault();
  clearContainers();
  const formData = new FormData();
  const inputs = form.querySelectorAll('input, select, textarea');


  // Dynamically get the current list of image containers
  const currentImageContainers = imageShelf.querySelectorAll('.image-container');

  // Append each image file to formData
  Array.from(currentImageContainers).forEach(container => {
    const img = container.querySelector('.image-preview');
    if (img && img.file) {  // Ensure the file exists and is not null
      formData.append('images', img.file);
    }
  });

  // Append other form data dynamically
  inputs.forEach(input => {
    if (input.type === 'file') {
      // Assuming you handle file inputs separately as shown above
    } else if (input.type !== 'submit' && input.name) {
      formData.append(input.name, input.value);
    }
  });
  showProgressBar();
  // Send data to Flask backend
  fetch('/api/generate-video', {
    method: 'POST',
    body: formData
  })
    .then(response => {
      if (response.ok) {
        return response.json();
      } else {
        hideProgressBar();
        throw new Error('Failed to initiate video generation process.');
      }
    })
    .then(data => {
      const sessionId = data.session_id; // Capture the session_id
      setupEventSource(sessionId); // Pass the session_id to the setupEventSource function
    })
    .catch(error => {
      hideProgressBar();
      console.error('Error:', error);
      alert('An error occurred while generating the video.');
    });
});

