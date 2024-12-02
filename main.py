import logging
import base64
import requests
import os
from flask import Flask, request, render_template_string, url_for
from werkzeug.utils import secure_filename
import pyttsx3
from gtts import gTTS

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants for file upload
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

class AccessibleImageDescriber:
    def __init__(self, logger):
        self.logger = logger
        self.api_key = os.getenv('OPENAI_API_KEY')
        self.model = "gpt-4o-mini"

    def encode_image_url(self, image_url):
        try:
            response = requests.get(image_url)
            return base64.b64encode(response.content).decode('utf-8')
        except Exception as e:
            self.logger.error(f"Error encoding image URL: {str(e)}")
            return None

    def encode_image_file(self, image_path):
        try:
            with open(image_path, 'rb') as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')
        except Exception as e:
            self.logger.error(f"Error encoding image file: {str(e)}")
            return None

    def describe_image(self, image_input, is_url=True):
        try:
            # Encode the image
            if is_url:
                base64_image = self.encode_image_url(image_input)
            else:
                base64_image = self.encode_image_file(image_input)

            if not base64_image:
                return "Error: Could not encode image"

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }

            # First prompt - Get initial description
            initial_payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Provide a detailed description of this image for visually impaired users. Start with the main subject(s) or object(s), then describe their location from left to right, top to bottom. Include:\n1. **Main subjects/objects**: Describe what they are and their actions if any.\n2. **Locations**: Specify where things are in relation to each other.\n3. **Colors and Patterns**: Describe colors and any visible patterns or textures.\n4. **Text**: If there is any text in the image, read it out or describe its appearance.\n5. **Environment/Ambience**: Describe the setting or scene, including lighting, weather, or any notable background elements.\n6. **Human Feelings**: If applicable, mention any emotions conveyed by human subjects.\n\nPlease avoid metaphors, idioms, or subjective terms that might not be clear to someone without visual experience."
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                "max_tokens": 300
            }

            initial_response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=initial_payload
            )

            if initial_response.status_code != 200:
                self.logger.error(f"API Error: {initial_response.status_code} - {initial_response.text}")
                return f"Error: API returned status code {initial_response.status_code}"

            initial_description = initial_response.json()['choices'][0]['message']['content']

            # Second prompt - Enhance for visually impaired users
            enhance_payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": f"Using the following description, craft an image description optimized for an app used by visually impaired individuals. Ensure the description:\n- Starts with the main subject, describing what it is, its location, and what it's doing.\n- Moves from left to right, top to bottom, detailing the surrounding elements.\n- Describes colors, textures, and any notable patterns in a way that can be understood through touch or other senses.\n- Avoids subjective terms or metaphors; use straightforward, factual language.\n- Reads out any visible text or describes its appearance.\n- Mentions any actions, movements, or emotions in a clear manner.\n\nHere's a template:\n'The main subject is a [[TYPE OF OBJECT]], located in the [[POSITION]]. It is [[COLOR]], with a [[TEXTURE]] texture. To its left, there is [[DESCRIPTION OF LEFT ELEMENTS]]. To its right, [[DESCRIPTION OF RIGHT ELEMENTS]]. Above, [[TOP ELEMENTS]]. Below, [[BOTTOM ELEMENTS]]. The ambient environment is [[AMBIENCE]].'\n\nDescription to enhance: {initial_description}"
                    }
                ],
                "max_tokens": 300
            }

            enhance_response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=enhance_payload
            )

            if enhance_response.status_code == 200:
                return enhance_response.json()['choices'][0]['message']['content']
            else:
                self.logger.error(f"API Error: {enhance_response.status_code} - {enhance_response.text}")
                return initial_description

        except Exception as e:
            self.logger.error(f"Error describing image: {str(e)}")
            return f"Error: {str(e)}"

    def text_to_speech(self, text, output_file="static/description.mp3"):
        try:
            tts = gTTS(text=text, lang='en')
            tts.save(output_file)
            return True
        except Exception as e:
            self.logger.error(f"Error converting text to speech: {str(e)}")
            return False

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
describer = AccessibleImageDescriber(logger)

# Ensure upload folders exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs('static', exist_ok=True)

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <title>EyeSpeak - Visual Assistant</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <style>
        /* Your existing CSS styles remain the same */
        /* Add this new style for the clear button */
        .clear-btn {
            background-color: #dc3545;
            margin-top: 10px;
        }
    </style>
</head>
<body>
    <h1><i class="fas fa-eye"></i> EyeSpeak - Visual Assistant</h1>
    
    <div class="container">
        <form method="POST" enctype="multipart/form-data" id="descriptionForm">
            <div class="input-group">
                <label for="image_url">
                    <i class="fas fa-link"></i> Enter Image URL:
                </label>
                <input type="text" id="image_url" name="image_url" 
                       placeholder="https://example.com/image.jpg"
                       aria-label="Enter image URL">
            </div>
            
            <div class="input-group">
                <label for="image_file">
                    <i class="fas fa-upload"></i> Upload Image
                </label>
                <div class="file-upload" id="dropZone">
                    <input type="file" id="image_file" name="image_file" 
                           accept=".jpg,.jpeg,.png,.gif" 
                           style="display: none;">
                    <i class="fas fa-cloud-upload-alt fa-3x"></i>
                    <p>Click or drag image here</p>
                </div>
            </div>

            <img id="imagePreview" class="preview-image" alt="Image preview">
            
            <button type="submit" class="submit-btn">
                <i class="fas fa-magic"></i> Describe Image
            </button>
            <button type="button" class="submit-btn clear-btn" id="clearButton">
                <i class="fas fa-trash"></i> Clear
            </button>
        </form>
        
        <div class="loading" id="loadingIndicator">
            <p><i class="fas fa-spinner fa-spin"></i> Processing image...</p>
            <div class="loading-bar"></div>
        </div>
    </div>

    {% if description %}
    <div class="container" id="descriptionContainer">
        <h2><i class="fas fa-comment-alt"></i> Description:</h2>
        <div class="description-container">
            {{ description }}
        </div>
        <div class="audio-player">
            <h3><i class="fas fa-volume-up"></i> Listen to Description:</h3>
            <audio controls style="width: 100%;">
                <source src="{{ url_for('static', filename='description.mp3') }}" type="audio/mpeg">
                Your browser does not support the audio element.
            </audio>
        </div>
    </div>
    {% endif %}

    <script>
        // Image preview functionality
        function handleFileSelect(event) {
            const file = event.target.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = function(e) {
                    const preview = document.getElementById('imagePreview');
                    preview.src = e.target.result;
                    preview.style.display = 'block';
                }
                reader.readAsDataURL(file);
            }
        }

        // URL preview functionality
        document.getElementById('image_url').addEventListener('change', function() {
            const preview = document.getElementById('imagePreview');
            preview.src = this.value;
            preview.style.display = 'block';
        });

        // Clear functionality
        document.getElementById('clearButton').addEventListener('click', function() {
            // Clear form inputs
            document.getElementById('image_url').value = '';
            document.getElementById('image_file').value = '';
            
            // Clear image preview
            const preview = document.getElementById('imagePreview');
            preview.src = '';
            preview.style.display = 'none';
            
            // Clear description if exists
            const descriptionContainer = document.getElementById('descriptionContainer');
            if (descriptionContainer) {
                descriptionContainer.style.display = 'none';
            }
        });

        // Form submission handling with fetch
        document.getElementById('descriptionForm').addEventListener('submit', function(e) {
            e.preventDefault();
            document.getElementById('loadingIndicator').style.display = 'block';
            
            const formData = new FormData(this);
            
            fetch('/', {
                method: 'POST',
                body: formData
            })
            .then(response => response.text())
            .then(html => {
                const parser = new DOMParser();
                const doc = parser.parseFromString(html, 'text/html');
                
                // Update only the description container
                const newDescription = doc.getElementById('descriptionContainer');
                if (newDescription) {
                    let existingDescription = document.getElementById('descriptionContainer');
                    if (existingDescription) {
                        existingDescription.innerHTML = newDescription.innerHTML;
                    } else {
                        document.body.appendChild(newDescription);
                    }
                }
                
                document.getElementById('loadingIndicator').style.display = 'none';
            })
            .catch(error => {
                console.error('Error:', error);
                document.getElementById('loadingIndicator').style.display = 'none';
            });
        });

        // File input and drag-drop handling
        document.getElementById('image_file').addEventListener('change', handleFileSelect);
        
        const dropZone = document.getElementById('dropZone');
        
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, preventDefaults, false);
        });

        function preventDefaults (e) {
            e.preventDefault();
            e.stopPropagation();
        }

        ['dragenter', 'dragover'].forEach(eventName => {
            dropZone.addEventListener(eventName, highlight, false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, unhighlight, false);
        });

        function highlight(e) {
            dropZone.classList.add('highlight');
        }

        function unhighlight(e) {
            dropZone.classList.remove('highlight');
        }

        dropZone.addEventListener('drop', handleDrop, false);

        function handleDrop(e) {
            const dt = e.dataTransfer;
            const files = dt.files;
            document.getElementById('image_file').files = files;
            handleFileSelect({target: {files: files}});
        }
    </script>
</body>
</html>
'''

@app.route('/', methods=['GET', 'POST'])
def home():
    description = None
    if request.method == 'POST':
        # Delete old audio file if exists
        audio_file = os.path.join('static', 'description.mp3')
        if os.path.exists(audio_file):
            os.remove(audio_file)
            
        if 'image_file' in request.files and request.files['image_file'].filename != '':
            file = request.files['image_file']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                description = describer.describe_image(filepath, is_url=False)
                # Clean up the uploaded file
                os.remove(filepath)
        elif request.form['image_url']:
            image_url = request.form['image_url']
            description = describer.describe_image(image_url, is_url=True)
        
        if description and not description.startswith('Error'):
            describer.text_to_speech(description)
    
    return render_template_string(HTML_TEMPLATE, description=description)

if __name__ == '__main__':
    app.run(debug=True)
