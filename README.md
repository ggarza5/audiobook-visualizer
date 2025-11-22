# Audiobook Visualizer - Real-time Story Visualization

This application listens to audiobooks playing through your computer's microphone and generates visual images in real-time that correspond to the story content. It uses AI to transcribe audio, detect semantic shifts (new characters, settings, events), and automatically generate relevant images.

## Features

- **Real-time Audio Capture**: Listens to audio from your computer's microphone
- **Speech Transcription**: Uses OpenAI Whisper API to convert audio to text
- **Semantic Analysis**: Detects new characters, settings, and story events using Gemini AI
- **Image Generation**: Automatically generates images using Gemini 2.5 Flash Image API when semantic shifts are detected
- **Context Tracking**: Maintains story context (characters, settings, events) throughout the session

## How It Works

1. **Audio Capture**: The app records audio from your microphone in 10-second chunks
2. **Transcription**: Each audio chunk is transcribed to text using OpenAI's Whisper API
3. **Semantic Analysis**: The transcribed text is analyzed by Gemini to detect:
   - New characters introduced
   - New settings or locations
   - Significant story events or plot developments
4. **Image Generation**: When semantic shifts are detected, Gemini 2.5 Flash Image generates a visual representation of the new content

## Setup

1. If you don't have Python installed, install it [from Python.org](https://www.python.org/downloads/).

2. [Clone](https://docs.github.com/en/repositories/creating-and-managing-repositories/cloning-a-repository) this repository.

3. Create a new virtual environment:

   - macOS/Linux:
     ```bash
     $ python -m venv venv
     $ source venv/bin/activate
     ```

   - Windows:
     ```cmd
     > python -m venv venv
     > .\venv\Scripts\activate
     ```

4. Install the requirements:

   ```bash
   $ pip install -r requirements.txt
   ```

5. Create a `.env` file in the root directory with your API keys:

   ```bash
   GOOGLE_API_KEY=your_gemini_api_key_here
   OPENAI_API_KEY=your_openai_api_key_here
   ```

   You can get your API keys from:
   - [Google AI Studio](https://ai.google.dev/gemini-api/docs/api-key) for Gemini API
   - [OpenAI Platform](https://platform.openai.com/api-keys) for Whisper API

6. Run the app:

   ```bash
   $ flask run
   ```

7. Open your browser and navigate to [http://localhost:5000](http://localhost:5000)

## Usage

1. **Start Listening**: Click the "Start Listening" button to begin capturing audio from your microphone
2. **Play Audiobook**: Play your audiobook through your computer's speakers (the microphone will pick it up)
3. **View Results**: 
   - Transcriptions appear in real-time as the story progresses
   - Generated images appear automatically when new story elements are detected
   - The context panel shows tracked characters, settings, and events
4. **Reset**: Click "Reset Context" to clear the story context and start fresh

## Technical Details

### Audio Processing
- Records audio in 10-second chunks using Web Audio API
- Sends audio as WebM format to the server
- Whisper API handles the transcription

### Semantic Shift Detection
- Uses Gemini 2.0 Flash Exp model to analyze transcriptions
- Compares new content against existing story context
- Identifies genuinely new elements (not just repetitions)

### Image Generation
- Uses Gemini 2.5 Flash Image model for fast image generation
- Generates images only when semantic shifts are detected
- Images are displayed inline with transcriptions

## Requirements

- Python 3.8+
- Flask
- Google Gen AI SDK
- OpenAI Python SDK
- Modern web browser with microphone access

## API Keys

This application requires two API keys:

1. **Google Gemini API Key**: For semantic analysis and image generation
   - Get it from: https://ai.google.dev/gemini-api/docs/api-key
   - Used for: Story analysis and image generation

2. **OpenAI API Key**: For audio transcription
   - Get it from: https://platform.openai.com/api-keys
   - Used for: Speech-to-text transcription

## Troubleshooting

- **Microphone not working**: Ensure your browser has permission to access the microphone
- **No transcriptions**: Check that your OpenAI API key is valid and you have credits
- **No images generated**: Verify your Google API key is correct and the Gemini Image API is available
- **Audio quality issues**: Ensure your audiobook is playing at a reasonable volume and there's minimal background noise

## License

See LICENSE file for details.
