import logging
import base64
import requests
import json
import os
from flask import Flask, request, jsonify, render_template_string

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ImageStoryGenerator:
    def __init__(self, logger):
        self.logger = logger
        self.api_key = os.getenv('OPENAI_API_KEY')
        self.model = "gpt-4o-mini"
        self.temperature = 0.5
        self.max_tokens = 400
        self.cache = {}

        self.image_processing_prompt = """
        You are an expert in analyzing and describing visual imagery. Your task is to provide a detailed, rich, and descriptive analysis of the provided image that highlights its key features, elements, and any potential themes or moods it might evoke.

        Instructions:
        - Review the image and identify the key visual elements and features (e.g., colors, shapes, textures, composition, etc.).
        - Describe the visual appearance of each person, including their clothing and any distinct characteristics.
        - Return the description of each person in a list format.
        """

    def process_image(self, image_data):
        self.logger.info("Processing image attachment")
        try:
            encoded_image = base64.b64encode(image_data).decode("utf-8")
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": self.image_processing_prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded_image}"}}
                        ]
                    }
                ],
                "max_tokens": self.max_tokens
            }
            response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
            response.raise_for_status()
            result = response.json()
            descriptions = result['choices'][0]['message']['content'].split('\n')
            return descriptions
        
        except Exception as e:
            self.logger.error(f"Error processing image: {e}")
            if 'response' in locals():
                self.logger.error(f"Response: {response.text}")
            return []

    def generate_story_from_image(self, image_data, people_names, genre, desired_length):
        self.logger.info("Generating story from image")
        image_content = self.process_image(image_data)
        names_list = ", ".join(people_names)

        story_prompt = f"""
        Based on the following image description and the provided character names: {names_list}, create a short story in the first person that is engaging and creative for a {genre} audience. The story should be no more than {desired_length} words.

        Image Description:
        {image_content}
        """
        
        try:
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}"
                },
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": story_prompt}],
                    "max_tokens": self.max_tokens,
                    "temperature": self.temperature
                }
            )
            response.raise_for_status()
            result = response.json()
            story = result['choices'][0]['message']['content']
            return story
        except Exception as e:
            self.logger.error(f"Error generating story: {e}")
            if 'response' in locals():
                self.logger.error(f"Response: {response.text}")
            return "Error generating story."

app = Flask(__name__)
image_story_generator = ImageStoryGenerator(logger)

@app.route('/')
def home():
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css">
        <title>Image Story Generator</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                background-color: #f4f4f4;
            }
            .container {
                max-width: 600px;
                margin: 50px auto;
                background: white;
                padding: 20px;
                border-radius: 8px;
                box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
            }
            .title {
                font-size: 2.5rem;
                font-weight: bold;
                color: #333;
                text-align: center;
                font-family: 'Courier New', Courier, monospace;
            }
            .explanation {
                margin-top: 20px;
                font-size: 1rem;
                color: #555;
                text-align: center;
                font-family: 'Courier New', Courier, monospace; /* Typewriter font */
            }
            #loadingMessage {
                display: none; /* Hidden by default */
                text-align: center;
                font-size: 1.2rem;
                margin-top: 20px;
                color: #007bff; /* Bootstrap primary color */
            }
        </style>
    </head>
    <body>
        <div class="container mt-5">
            <h1 class="title">Image Story Generator</h1>
            <form id="storyForm" action="/generate_story" method="POST" enctype="multipart/form-data" onsubmit="return validateForm()">
                <div class="form-group">
                    <label for="image">Upload Image:</label>
                    <input type="file" class="form-control" name="image" accept="image/*" required>
                </div>
                <div class="form-group">
                    <label for="names">Names (comma separated):</label>
                    <input type="text" class="form-control" name="names" placeholder="Enter names, e.g. Stephen, Jude etc." required>
                </div>
                <div class="form-group">
                    <label for="genre">Genre:</label>
                    <input type="text" class="form-control" name="genre" placeholder="Enter genre or theme, set the scene!" required>
                </div>
                <div class="form-group">
                    <label for="length">Desired Length (in words):</label>
                    <input type="number" class="form-control" name="length" required min="10">
                </div>
                <button type="submit" class="btn btn-primary btn-lg btn-block">Generate Story</button>
                <div id="loadingMessage">Generating story...</div>
            </form>
            <p class="explanation">
                This application utilizes a single large language model (LLM) that leverages advanced natural language processing (NLP) techniques. It first interprets the uploaded image, analyzing key visual features and elements through image processing APIs. The model then generates an engaging narrative by combining these visual interpretations with user-defined parameters, including character names, genre, and desired story length. This integration of multimodal data allows for the creation of contextually relevant and imaginative stories, demonstrating the powerful capabilities of LLMs in bridging visual and textual information.
            </p>
        </div>
        <script>
            function validateForm() {
                document.getElementById('loadingMessage').style.display = 'block'; // Show loading message
                return true; 
            }
        </script>
    </body>
    </html>
    """)

@app.route('/generate_story', methods=['POST'])
def generate_story():
    # Get the input data from the request
    image_file = request.files.get('image')

    if not image_file:
        return jsonify({'error': 'No image file provided'}), 400

    people_names = request.form.getlist('names')
    genre = request.form.get('genre', 'general')
    desired_length = int(request.form.get('length', 200))

    # Read the image data
    image_data = image_file.read()
    # Generate the story based on the input data
    story = image_story_generator.generate_story_from_image(image_data, people_names, genre, desired_length)

    # Encode image for displaying in HTML
    encoded_image = base64.b64encode(image_data).decode("utf-8")

    # Check if the story was generated successfully or an error occurred
    if "Error generating story" in story:
        return jsonify({'error': story}), 500

    # Create an HTML page displaying the image and the story
    return render_template_string(f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css">
        <style>
            .story-container {{
                display: flex;
                justify-content: space-around;
                align-items: flex-start;
                margin-top: 20px;
            }}
            .story-image {{
                max-width: 300px;
                border: 1px solid #ccc;
                border-radius: 8px;
            }}
            .story-text {{
                max-width: 600px;
                padding: 15px;
                background-color: #f8f9fa;
                border: 1px solid #888;
                border-radius: 8px;
                box-shadow: 0 0 10px rgba(0,0,0,0.1);
                font-family: 'Courier New', Courier, monospace; /* Typewriter font for story */
            }}
        </style>
    </head>
    <body>
        <div class="container mt-5">
            <h1 class="text-center">Generated Story</h1>
            <div class="story-container">
                <div class="story-image">
                    <img src="data:image/jpeg;base64,{encoded_image}" class="img-fluid" alt="Uploaded Image">
                </div>
                <div class="story-text">
                    <h3>Your Story:</h3>
                    <p>{story}</p>
                </div>
            </div>
            <div class="text-center mt-3">
                <a class="btn btn-primary" href="/">Generate Another Story</a>
            </div>
        </div>
    </body>
    </html>
    """)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
