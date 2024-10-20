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

        # Prompt for the image processing API
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
                self.logger.error(f"Response: {response.text}")  # Log the full response if available
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
                self.logger.error(f"Response: {response.text}")  # Log the full response if available
            return "Error generating story."

app = Flask(__name__)
image_story_generator = ImageStoryGenerator(logger)

#@app.route('/')
#def home():
    #return render_template_string("""
    #<h1>Welcome to Image Story Generator</h1>
    #<p>Use the /generate_story endpoint to generate a story from an image.</p>
    #""")
@app.route('/')
def home():
    return render_template_string("""
    <h1>Welcome to Image Story Generator</h1>
    <form action="/generate_story" method="post" enctype="multipart/form-data">
        <input type="file" name="image" required><br><br>
        <label for="names">Names:</label>
        <input type="text" name="names" required><br><br>
        <label for="genre">Genre:</label>
        <input type="text" name="genre" required><br><br>
        <label for="length">Desired Length:</label>
        <input type="number" name="length" required><br><br>
        <input type="submit" value="Generate Story">
    </form>
    """)

@app.route('/generate_story', methods=['POST'])
def generate_story():
    # Get the input data from the request
    image_file = request.files.get('image')
    people_names = request.form.getlist('names')
    genre = request.form.get('genre', 'general')
    desired_length = int(request.form.get('length', 200))

    if not image_file:
        return jsonify({'error': 'No image file provided'}), 400

    # Generate the story based on the input data
    story = image_story_generator.generate_story_from_image(image_file.read(), people_names, genre, desired_length)

    # Return the story as a JSON response
    return jsonify({'story': story})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
