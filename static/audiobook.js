// Audio recording and visualization system
let mediaRecorder = null;
let audioChunks = [];
let isRecording = false;
let recordingInterval = null;
let contextUpdateInterval = null;

const recordBtn = document.getElementById('record-btn');
const resetBtn = document.getElementById('reset-btn');
const recordingStatus = document.getElementById('recording-status');
const messagesContainer = document.getElementById('messages-container');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    recordBtn.addEventListener('click', toggleRecording);
    resetBtn.addEventListener('click', resetContext);
    updateContext();
    
    // Update context periodically
    contextUpdateInterval = setInterval(updateContext, 5000);
});

async function toggleRecording() {
    if (!isRecording) {
        await startRecording();
    } else {
        stopRecording();
    }
}

async function startRecording() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream, {
            mimeType: 'audio/webm;codecs=opus'
        });
        
        audioChunks = [];
        
        mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0) {
                audioChunks.push(event.data);
            }
        };
        
        mediaRecorder.onstop = async () => {
            await processAudioChunk();
        };
        
        // Record in chunks (every 10 seconds)
        mediaRecorder.start();
        recordingInterval = setInterval(() => {
            if (mediaRecorder.state === 'recording') {
                mediaRecorder.stop();
                mediaRecorder.start();
            }
        }, 10000);
        
        isRecording = true;
        recordBtn.textContent = 'Stop Listening';
        recordBtn.classList.add('recording');
        recordingStatus.textContent = 'Recording...';
        recordingStatus.classList.add('active');
        
    } catch (error) {
        console.error('Error accessing microphone:', error);
        alert('Error accessing microphone. Please check permissions.');
    }
}

function stopRecording() {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
        mediaRecorder.stop();
        mediaRecorder.stream.getTracks().forEach(track => track.stop());
    }
    
    if (recordingInterval) {
        clearInterval(recordingInterval);
        recordingInterval = null;
    }
    
    isRecording = false;
    recordBtn.textContent = 'Start Listening';
    recordBtn.classList.remove('recording');
    recordingStatus.textContent = 'Stopped';
    recordingStatus.classList.remove('active');
}

async function processAudioChunk() {
    if (audioChunks.length === 0) return;
    
    const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
    audioChunks = []; // Clear chunks after processing
    
    // Send webm directly - Whisper API supports webm format
    const formData = new FormData();
    formData.append('audio', audioBlob, 'audio.webm');
    
    try {
        const response = await fetch('/transcribe', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        // Debug logging
        console.log('Transcription response:', {
            success: result.success,
            has_semantic_shift: result.has_semantic_shift,
            has_image: !!result.image,
            image_size: result.image ? result.image.length : 0,
            image_preview: result.image ? result.image.substring(0, 50) + '...' : 'none',
            analysis: result.analysis
        });
        
        if (result.success) {
            displayTranscription(result);
            
            if (result.has_semantic_shift) {
                console.log('Semantic shift detected!', result.analysis);
                if (result.image) {
                    console.log('Image generated, displaying...');
                    displayImage(result);
                } else {
                    console.warn('Semantic shift detected but no image in response');
                }
            } else {
                console.log('No semantic shift detected');
            }
        } else {
            console.error('Transcription error:', result.message);
        }
    } catch (error) {
        console.error('Error processing audio:', error);
    }
}


function displayTranscription(result) {
    const transcriptionDiv = document.createElement('div');
    transcriptionDiv.className = 'transcription-entry';
    
    const timestamp = new Date().toLocaleTimeString();
    transcriptionDiv.innerHTML = `
        <div class="transcription-header">
            <span class="timestamp">${timestamp}</span>
            ${result.has_semantic_shift ? '<span class="shift-badge">New Content Detected</span>' : ''}
        </div>
        <div class="transcription-text">${escapeHtml(result.transcription)}</div>
    `;
    
    messagesContainer.insertBefore(transcriptionDiv, messagesContainer.firstChild);
    
    // Scroll to top to show latest
    messagesContainer.scrollTop = 0;
}

function displayImage(result) {
    console.log('displayImage called with:', {
        has_image: !!result.image,
        image_length: result.image ? result.image.length : 0,
        image_prompt: result.image_prompt
    });
    
    if (!result.image) {
        console.error('No image data in result');
        return;
    }
    
    const imageDiv = document.createElement('div');
    imageDiv.className = 'generated-image-entry';
    
    const timestamp = new Date().toLocaleTimeString();
    const imageSrc = `data:image/png;base64,${result.image}`;
    
    console.log('Creating image with src length:', imageSrc.length);
    
    imageDiv.innerHTML = `
        <div class="image-header">
            <span class="timestamp">${timestamp}</span>
            <span class="image-label">Generated Visual</span>
        </div>
        <div class="image-prompt">${escapeHtml(result.image_prompt)}</div>
        <img src="${imageSrc}" alt="Generated image" class="generated-image" onerror="console.error('Image failed to load')" onload="console.log('Image loaded successfully')" />
    `;
    
    messagesContainer.insertBefore(imageDiv, messagesContainer.firstChild);
    messagesContainer.scrollTop = 0;
    
    console.log('Image element added to DOM');
}

async function resetContext() {
    try {
        const response = await fetch('/reset', {
            method: 'POST'
        });
        
        const result = await response.json();
        
        if (result.success) {
            // Clear messages
            messagesContainer.innerHTML = `
                <div class="welcome-message">
                    <h2>Context Reset</h2>
                    <p>Story context has been cleared. Start listening to begin a new story.</p>
                </div>
            `;
            
            // Update context display
            updateContext();
        }
    } catch (error) {
        console.error('Error resetting context:', error);
    }
}

async function updateContext() {
    try {
        const response = await fetch('/status');
        const status = await response.json();
        
        // Update context display
        const charactersList = document.getElementById('characters-list');
        const settingsList = document.getElementById('settings-list');
        const eventsList = document.getElementById('events-list');
        
        charactersList.textContent = status.context.characters.length > 0 
            ? status.context.characters.join(', ') 
            : 'None';
        
        settingsList.textContent = status.context.settings.length > 0 
            ? status.context.settings.join(', ') 
            : 'None';
        
        eventsList.textContent = status.context.recent_events.length > 0 
            ? status.context.recent_events.slice(-5).join(', ') 
            : 'None';
            
    } catch (error) {
        console.error('Error updating context:', error);
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

