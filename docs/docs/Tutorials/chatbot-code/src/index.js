console.log('ChatInterface script loaded');

// --- State ---
const sessionId = 'user_' + Date.now();
const flowId = '05f71567-8cde-44a7-b999-0b834a3b2386';
const hostUrl = 'http://localhost:7861';

// --- DOM Elements ---
let input, button, messagesContainer;

// --- Initialization ---
document.addEventListener('DOMContentLoaded', () => {
    input = document.getElementById('messageInput');
    button = document.getElementById('sendButton');
    messagesContainer = document.getElementById('chatMessages');

    setupEventListeners();
    addBotMessage("Hello! I'm your TechCorp support assistant. How can I help you today?");
});

// --- Event Listeners ---
function setupEventListeners() {
    button.addEventListener('click', handleSend);
    input.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') handleSend();
    });
}

function handleSend() {
    const message = input.value.trim();
    if (message) {
        sendMessage(message);
        input.value = '';
    }
}

// --- Chat Logic ---
function sendMessage(message) {
    addUserMessage(message);
    addTypingIndicator();
    setInputState(false);

    callLangflowAPI(message)
        .then(response => {
            removeTypingIndicator();
            if (response) {
                addBotMessage(response);
            } else {
                addBotMessage("Sorry, I'm having trouble connecting right now. Please check your connection and try again.");
            }
        })
        .catch(error => {
            removeTypingIndicator();
            addBotMessage(`Sorry, I encountered an error: ${error.message}`);
            console.error('Error details:', error);
        })
        .finally(() => {
            setInputState(true);
        });
}

async function callLangflowAPI(message) {
    // For demo: prompt for API key if not in localStorage
    let apiKey = localStorage.getItem('LANGFLOW_API_KEY');
    if (!apiKey) {
        apiKey = prompt('Please enter your Langflow API key:');
        if (apiKey) localStorage.setItem('LANGFLOW_API_KEY', apiKey);
    }
    if (!apiKey) return null;

    const payload = {
        "output_type": "chat",
        "input_type": "chat",
        "input_value": message,
        "session_id": sessionId
    };

    const options = {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            "x-api-key": apiKey
        },
        body: JSON.stringify(payload)
    };

    const response = await fetch(`${hostUrl}/api/v1/run/${flowId}`, options);
    if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`HTTP error! status: ${response.status}, message: ${errorText}`);
    }
    const data = await response.json();
    return extractMessage(data);
}

function extractMessage(response) {
    try {
        return response.outputs?.[0]?.outputs?.[0]?.results?.message?.text || null;
    } catch (error) {
        console.error('Error extracting message:', error);
        return null;
    }
}

// --- UI Helpers ---
function addUserMessage(text) {
    addMessage(text, 'user');
}

function addBotMessage(text) {
    addMessage(text, 'bot');
}

function addMessage(text, sender) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}-message`;
    messageDiv.textContent = text;
    messagesContainer.appendChild(messageDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function addTypingIndicator() {
    const typingDiv = document.createElement('div');
    typingDiv.className = 'typing-indicator';
    typingDiv.id = 'typing-indicator';
    typingDiv.innerHTML = `
        <span>Typing</span>
        <div class="typing-dots">
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
        </div>
    `;
    messagesContainer.appendChild(typingDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function removeTypingIndicator() {
    const typingIndicator = document.getElementById('typing-indicator');
    if (typingIndicator) typingIndicator.remove();
}

function setInputState(enabled) {
    input.disabled = !enabled;
    button.disabled = !enabled;
    if (enabled) input.focus();
}

function showError(message) {
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error-message';
    errorDiv.textContent = message;
    messagesContainer.appendChild(errorDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}
