import logging
import base64
import requests
import os
import gradio as gr
from gtts import gTTS
import uuid
from PIL import Image
import tempfile

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AccessibleImageDescriber:
    def __init__(self, logger):
        self.logger = logger
        self.api_key = os.getenv('OPENAI_API_KEY')
        self.model = "gpt-4-vision-preview"

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

            initial_payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Provide a detailed description of this image for visually impaired users. Include main subjects, locations, colors, patterns, text if any, and environment/ambience."
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

            enhance_payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": f"Enhance this description for visually impaired users: {initial_description}"
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

def process_image(image, text_size="medium", image_size="medium", speech_speed="1.0"):
    """
    Process the image with customizable text and image sizes and speech speed
    """
    try:
        describer = AccessibleImageDescriber(logger)
        
        # Resize image based on selected size
        if image_size == "large":
            new_size = (800, 800)
        elif image_size == "small":
            new_size = (400, 400)
        else:  # medium
            new_size = (600, 600)
        
        # Create a copy of the image for resizing
        img_copy = image.copy()
        img_copy.thumbnail(new_size, Image.Resampling.LANCZOS)
        
        # Save temporary image
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_img:
            temp_path = temp_img.name
            img_copy.save(temp_path)
        
        # Get description
        description = describer.describe_image(temp_path, is_url=False)
        
        # Generate audio with specified speed
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_audio:
            audio_path = temp_audio.name
            if description and not description.startswith('Error'):
                tts = gTTS(text=description, lang='en', slow=(speech_speed == "0.75"))
                tts.save(audio_path)
        
        # Clean up temporary image file
        os.unlink(temp_path)
        
        # Apply text size styling
        if text_size == "large":
            description = f"<div style='font-size: 24px'>{description}</div>"
        elif text_size == "small":
            description = f"<div style='font-size: 14px'>{description}</div>"
        else:  # medium
            description = f"<div style='font-size: 18px'>{description}</div>"
        
        return description, audio_path
    
    except Exception as e:
        logger.error(f"Error in process_image: {str(e)}")
        return f"Error processing image: {str(e)}", None

def create_interface():
    # Custom CSS for better appearance and accessibility
    custom_css = """
    #image_box { min-height: 400px; }
    .gradio-container { max-width: 1200px; margin: auto; }
    .description-text { line-height: 1.6; }
    .controls-panel { padding: 20px; }
    """
    
    with gr.Blocks(css=custom_css, title="EyeSpeak - Visual Assistant") as demo:
        gr.Markdown(
            """
            # 👁️ EyeSpeak - Visual Assistant
            ### AI-Powered Image Description for Visual Accessibility
            """
        )
        
        with gr.Row():
            with gr.Column(scale=1):
                # Input components
                image_input = gr.Image(
                    type="pil",
                    label="Upload or Drop Image Here",
                    elem_id="image_box"
                )
                
                with gr.Row():
                    text_size = gr.Radio(
                        choices=["small", "medium", "large"],
                        value="medium",
                        label="Text Size",
                        interactive=True
                    )
                    image_size = gr.Radio(
                        choices=["small", "medium", "large"],
                        value="medium",
                        label="Image Size",
                        interactive=True
                    )
                    speech_speed = gr.Radio(
                        choices=["0.75", "1.0", "1.25"],
                        value="1.0",
                        label="Speech Speed",
                        interactive=True
                    )
                
                submit_btn = gr.Button(
                    "🔍 Describe Image",
                    variant="primary",
                    size="lg"
                )
            
            with gr.Column(scale=1):
                # Output components
                description_out = gr.HTML(
                    label="Image Description",
                    elem_classes="description-text"
                )
                audio_out = gr.Audio(
                    label="🔊 Listen to Description",
                    show_label=True
                )
        
        # Handle image processing
        submit_btn.click(
            fn=process_image,
            inputs=[image_input, text_size, image_size, speech_speed],
            outputs=[description_out, audio_out]
        )
        
        # Usage instructions
        gr.Markdown(
            """
            ### 📝 How to Use:
            1. Upload an image or drag and drop it into the image box
            2. Adjust text size, image size, and speech speed as needed
            3. Click the 'Describe Image' button
            4. Read the detailed description or listen to the audio version
            
            ### ℹ️ Features:
            - Adjustable text size for better readability
            - Customizable image size
            - Variable speech speed for audio playback
            - Detailed visual description optimized for screen readers
            - Text-to-speech audio generation
            - Support for various image formats
            """
        )
    
    return demo

# Create and launch the app
if __name__ == "__main__":
    # Launch the interface
    demo = create_interface()
    demo.launch(
        share=True,  # Enable sharing
        enable_queue=True,  # Enable queue for multiple users
        show_error=True,  # Show errors in the interface
        server_name="0.0.0.0",  # Make accessible from all network interfaces
        server_port=7860  # Default Gradio port
    )
