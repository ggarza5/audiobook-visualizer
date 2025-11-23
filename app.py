from flask import (
    Flask,
    render_template,
    request,
    Response,
    stream_with_context,
    jsonify,
)
from werkzeug.utils import secure_filename
from PIL import Image
import io
from dotenv import load_dotenv
import os
import base64
import tempfile
from datetime import datetime
from openai import OpenAI
from google import genai

# Load environment variables from .env file
load_dotenv()

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}

# Initialize clients with error handling
# Check for both GOOGLE_API_KEY and GCG_GOOGLE_API_KEY for flexibility
google_api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GCG_GOOGLE_API_KEY")
openai_api_key = os.getenv("OPENAI_API_KEY")

if not google_api_key:
    raise ValueError("GOOGLE_API_KEY or GCG_GOOGLE_API_KEY not found in environment. Please set it in your .env file.")
if not openai_api_key:
    raise ValueError("OPENAI_API_KEY not found in environment. Please set it in your .env file.")

genai_client = genai.Client(api_key=google_api_key)
openai_client = OpenAI(api_key=openai_api_key)

app = Flask(__name__, static_folder='static', template_folder='templates')

# Global state for audiobook visualization
recording_active = False
transcription_buffer = []
semantic_context = {
    "characters": [],
    "settings": [],
    "recent_events": []
}


def allowed_file(filename):
    """Returns if a filename is supported via its extension"""
    _, ext = os.path.splitext(filename)
    return ext.lstrip('.').lower() in ALLOWED_EXTENSIONS


def analyze_semantic_shifts(transcription_text):
    """
    Analyzes transcription text for semantic shifts (new characters, settings, events)
    Returns a dictionary with detected shifts
    """
    global semantic_context
    
    # Create prompt for semantic analysis
    context_summary = f"""
    You are analyzing an English-language audiobook transcription. The text below is in English.
    
    Current story context:
    - Characters: {', '.join(semantic_context['characters']) if semantic_context['characters'] else 'None'}
    - Settings: {', '.join(semantic_context['settings']) if semantic_context['settings'] else 'None'}
    - Recent events: {', '.join(semantic_context['recent_events'][-3:]) if semantic_context['recent_events'] else 'None'}
    
    New transcription (English): {transcription_text}
    
    Analyze this English transcription and identify:
    1. New characters introduced (names or descriptions)
    2. New settings or locations mentioned
    3. Significant story events or plot developments
    
    Respond in JSON format:
    {{
        "has_shift": true/false,
        "new_characters": ["character1", "character2"],
        "new_settings": ["setting1", "setting2"],
        "new_events": ["event1", "event2"],
        "image_prompt": "A detailed description for generating an image of the new semantic content"
    }}
    
    For the first transcription or if the context is empty, set has_shift to true if there are any characters, settings, or events mentioned.
    For subsequent transcriptions, set has_shift to true if there are genuinely new elements or significant developments.
    Always provide an image_prompt when has_shift is true.
    All text is in English - do not confuse it with other languages.
    """
    
    try:
        response = genai_client.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents=[context_summary]
        )
        
        # Parse the response (it should be JSON)
        import json
        import re
        
        # Extract JSON from response
        response_text = response.text
        print(f"Semantic analysis raw response: {response_text[:500]}")  # First 500 chars
        
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        
        if json_match:
            try:
                analysis = json.loads(json_match.group())
                print(f"Parsed analysis: {analysis}")
                
                # Update semantic context
                if analysis.get("new_characters"):
                    semantic_context["characters"].extend(analysis["new_characters"])
                    semantic_context["characters"] = list(set(semantic_context["characters"]))  # Remove duplicates
                
                if analysis.get("new_settings"):
                    semantic_context["settings"].extend(analysis["new_settings"])
                    semantic_context["settings"] = list(set(semantic_context["settings"]))
                
                if analysis.get("new_events"):
                    semantic_context["recent_events"].extend(analysis["new_events"])
                    # Keep only last 10 events
                    semantic_context["recent_events"] = semantic_context["recent_events"][-10:]
                
                return analysis
            except json.JSONDecodeError as e:
                print(f"Error parsing JSON from response: {e}")
                print(f"JSON match: {json_match.group()[:200]}")
                return {"has_shift": False}
        else:
            print("No JSON found in semantic analysis response")
            return {"has_shift": False}
    except Exception as e:
        print(f"Error in semantic analysis: {e}")
        return {"has_shift": False}


def generate_image(prompt):
    """
    Generates an image using Gemini 2.5 Flash Image API
    Returns base64 encoded image data
    """
    try:
        print(f"Calling Gemini image API with prompt: {prompt[:100]}...")
        response = genai_client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=[prompt]
        )
        
        print(f"Image API response received, type: {type(response)}")
        print(f"Response has candidates: {hasattr(response, 'candidates')}")
        
        # The response structure is: response.candidates[0].content.parts
        if hasattr(response, 'candidates') and response.candidates:
            print(f"Found {len(response.candidates)} candidates")
            for candidate in response.candidates:
                if hasattr(candidate, 'content'):
                    content = candidate.content
                    if hasattr(content, 'parts'):
                        for part in content.parts:
                            # Try as_image() method first (PIL Image)
                            if hasattr(part, 'as_image'):
                                try:
                                    image = part.as_image()
                                    if image:
                                        buffer = io.BytesIO()
                                        image.save(buffer, format='PNG')
                                        image_bytes = buffer.getvalue()
                                        encoded = base64.b64encode(image_bytes).decode('utf-8')
                                        print(f"✓ Image generated and encoded, size: {len(encoded)} chars")
                                        return encoded
                                except Exception as e:
                                    print(f"Error with as_image(): {e}")
                            
                            # Try inline_data attribute
                            if hasattr(part, 'inline_data') and part.inline_data:
                                try:
                                    if hasattr(part.inline_data, 'data'):
                                        image_data = part.inline_data.data
                                        
                                        # Check the data type and handle accordingly
                                        if isinstance(image_data, bytes):
                                            # Check if bytes are actually a PNG (starts with PNG signature)
                                            if len(image_data) > 8 and image_data[:8] == b'\x89PNG\r\n\x1a\n':
                                                # It's raw PNG bytes, encode to base64 for JSON
                                                encoded = base64.b64encode(image_data).decode('utf-8')
                                                print(f"✓ Image generated from inline_data (raw PNG bytes), size: {len(encoded)} chars")
                                                return encoded
                                            else:
                                                # Might be base64-encoded string stored as bytes
                                                try:
                                                    decoded = base64.b64decode(image_data, validate=True)
                                                    if len(decoded) > 8 and decoded[:8] == b'\x89PNG\r\n\x1a\n':
                                                        # It was base64, now decoded to PNG bytes, encode again for JSON
                                                        encoded = base64.b64encode(decoded).decode('utf-8')
                                                        print(f"✓ Image generated from inline_data (base64 in bytes, decoded), size: {len(encoded)} chars")
                                                        return encoded
                                                except:
                                                    pass
                                                # Raw bytes but not PNG, encode anyway
                                                encoded = base64.b64encode(image_data).decode('utf-8')
                                                print(f"✓ Image generated from inline_data (raw bytes), size: {len(encoded)} chars")
                                                return encoded
                                        elif isinstance(image_data, str):
                                            # It's a string - likely already base64 encoded
                                            # Try to decode to verify it's valid base64 and contains PNG
                                            try:
                                                decoded = base64.b64decode(image_data, validate=True)
                                                if len(decoded) > 8 and decoded[:8] == b'\x89PNG\r\n\x1a\n':
                                                    # Valid base64 containing PNG, return as-is
                                                    print(f"✓ Image generated from inline_data (base64 string), size: {len(image_data)} chars")
                                                    return image_data
                                            except:
                                                pass
                                            # Not valid base64 or not PNG, but return anyway
                                            print(f"✓ Image generated from inline_data (string, assumed base64), size: {len(image_data)} chars")
                                            return image_data
                                except Exception as e:
                                    print(f"Error with inline_data: {e}")
                                    import traceback
                                    traceback.print_exc()
        
        print("✗ No image found in response structure")
        return None
    except Exception as e:
        print(f"Error generating image: {e}")
        import traceback
        traceback.print_exc()
        return None


@app.route("/", methods=["GET"])
def index():
    """Renders the main homepage for the app"""
    return render_template("index.html")


@app.route("/transcribe", methods=["POST"])
def transcribe_audio():
    """
    Receives audio data, transcribes it using Whisper API,
    analyzes for semantic shifts, and generates images if needed
    """
    global transcription_buffer
    
    try:
        # Get audio file from request
        if "audio" not in request.files:
            return jsonify(success=False, message="No audio file provided")
        
        audio_file = request.files["audio"]
        
        # Save to temporary file (accept webm or wav)
        # Whisper API supports various formats including webm
        file_ext = os.path.splitext(audio_file.filename)[1] if audio_file.filename else ".webm"
        if not file_ext:
            file_ext = ".webm"
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_file:
            audio_file.save(tmp_file.name)
            tmp_path = tmp_file.name
        
        try:
            # Transcribe using OpenAI Whisper API
            with open(tmp_path, "rb") as audio:
                transcript = openai_client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio,
                    response_format="text",
                    language="en"  # Explicitly set to English
                )
            
            # When response_format="text", transcript is already a string
            transcription_text = transcript if isinstance(transcript, str) else str(transcript)
            transcription_buffer.append({
                "text": transcription_text,
                "timestamp": datetime.now().isoformat()
            })
            
            # Analyze for semantic shifts
            analysis = analyze_semantic_shifts(transcription_text)
            
            print(f"Semantic analysis result: has_shift={analysis.get('has_shift')}, prompt={analysis.get('image_prompt')}")
            
            result = {
                "success": True,
                "transcription": transcription_text,
                "has_semantic_shift": analysis.get("has_shift", False),
                "analysis": analysis
            }
            
            # Generate image if semantic shift detected
            if analysis.get("has_shift") and analysis.get("image_prompt"):
                print(f"Generating image for semantic shift...")
                image_base64 = generate_image(analysis["image_prompt"])
                if image_base64:
                    result["image"] = image_base64
                    result["image_prompt"] = analysis["image_prompt"]
                    print(f"✓ Image added to response (size: {len(image_base64)} chars)")
                else:
                    print("✗ Warning: Image generation returned None")
                    print("  This means the API call succeeded but no image was found in the response")
            else:
                if not analysis.get("has_shift"):
                    print("No semantic shift detected, skipping image generation")
                elif not analysis.get("image_prompt"):
                    print("Semantic shift detected but no image_prompt provided")
            
            # Log response summary before sending
            response_summary = {
                "success": result["success"],
                "has_semantic_shift": result.get("has_semantic_shift"),
                "has_image": "image" in result,
                "image_size": len(result.get("image", "")) if "image" in result else 0,
                "transcription_length": len(result.get("transcription", ""))
            }
            print(f"Response summary: {response_summary}")
            
            return jsonify(result)
            
        finally:
            # Clean up temporary file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
                
    except Exception as e:
        print(f"Error in transcription: {e}")
        return jsonify(success=False, message=str(e)), 500


@app.route("/reset", methods=["POST"])
def reset_context():
    """Resets the semantic context"""
    global semantic_context, transcription_buffer
    semantic_context = {
        "characters": [],
        "settings": [],
        "recent_events": []
    }
    transcription_buffer = []
    return jsonify(success=True)


@app.route("/status", methods=["GET"])
def get_status():
    """Returns current status and context"""
    return jsonify({
        "recording_active": recording_active,
        "transcription_count": len(transcription_buffer),
        "context": semantic_context
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
