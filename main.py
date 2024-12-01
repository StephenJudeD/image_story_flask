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
                                "text": "What do you see in this image? Provide a detailed description."
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
                        "content": f"Please enhance this description for a visually impaired person, making it more detailed and descriptive, focusing on spatial relationships and important details: {initial_description}"
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
<html>
<head>
    <title>Image Description Service</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
        }
        .container {
            background-color: #f5f5f5;
            padding: 20px;
            border-radius: 5px;
            margin-top: 20px;
        }
        .description {
            margin-top: 20px;
            padding: 10px;
            background-color: white;
            border-radius: 5px;
        }
        .or-divider {
            text-align: center;
            margin: 20px 0;
            font-weight: bold;
        }
    </style>
</head>
<body>
    <h1>Image Description Service</h1>
    <div class="container">
        <form method="POST" enctype="multipart/form-data">
            <label for="image_url">Enter Image URL:</label><br>
            <input type="text" id="image_url" name="image_url" style="width: 100%;"><br><br>
            
            <div class="or-divider">OR</div>
            
            <label for="image_file">Upload Image File:</label><br>
            <input type="file" id="image_file" name="image_file" accept=".jpg,.jpeg,.png,.gif"><br><br>
            
            <input type="submit" value="Describe Image">
        </form>
    </div>
    {% if description %}
    <div class="container">
        <h2>Description:</h2>
        <div class="description">
            {{ description }}
        </div>
        <audio controls style="margin-top: 20px;">
            <source src="{{ url_for('static', filename='description.mp3') }}" type="audio/mpeg">
            Your browser does not support the audio element.
        </audio>
    </div>
    {% endif %}
</body>
</html>
'''

@app.route('/', methods=['GET', 'POST'])
def home():
    description = None
    if request.method == 'POST':
        # Check if the post request has the file part
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
