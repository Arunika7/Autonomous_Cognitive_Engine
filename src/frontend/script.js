const API_URL = 'http://localhost:8000';
let state = null;
let session_id = localStorage.getItem("session_id");
if (!session_id) {
    session_id = crypto.randomUUID();
    localStorage.setItem("session_id", session_id);
}

async function sendMessage() {
    const input = document.getElementById('userInput');
    const message = input.value.trim();
    if (!message) return;
    input.disabled = true;
    document.getElementById('sendBtn').disabled = true;
    addMessage('user', message);
    input.value = '';
    showTypingIndicator();
    try {
        const response = await fetch(`${API_URL}/chat`, {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'X-API-Key': 'default-secret-key-change-in-production'
            },
            body: JSON.stringify({
                session_id: session_id,
                message: message
            })
        });
        if (!response.ok) throw new Error('API request failed');
        const data = await response.json();
        hideTypingIndicator();
        // Update state
        state = {
            todos: data.todos,
            files: data.files,
            calendar: data.calendar
        };
        // Show tool usage
        if (data.tool_calls && data.tool_calls.length > 0) {
            addMessage('system', `Tools used: ${data.tool_calls.join(', ')}`);
        }
        // Show response
        addMessage('assistant', data.response);
        // Update UI
        updateTodosList();
        updateFilesList();
        updateCalendarList();
        updateStats();
    } catch (error) {
        hideTypingIndicator();
        addMessage('assistant', `Error: ${error.message}`);
    }
    input.disabled = false;
    document.getElementById('sendBtn').disabled = false;
    input.focus();
}

function addMessage(role, content) {
    const div = document.getElementById('chatMessages');
    const msg = document.createElement('div');
    msg.className = 'message flex gap-3';
    if (role === 'user') {
        msg.innerHTML = `
            <div class="flex-1 flex justify-end">
                <div class="bg-blue-600 text-white rounded-lg shadow-sm p-4 max-w-3xl">
                    <div class="text-sm whitespace-pre-wrap">${escapeHtml(content)}</div>
                </div>
            </div>
            <div class="w-8 h-8 rounded-full bg-gray-600 flex items-center justify-center text-white flex-shrink-0">User</div>
        `;
    } else if (role === 'system') {
        msg.innerHTML = `
            <div class="flex-1">
                <div class="bg-gray-100 text-gray-600 rounded-lg p-2 text-xs text-center">${escapeHtml(content)}</div>
            </div>
        `;
    } else {
        msg.innerHTML = `
            <div class="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-white flex-shrink-0"></div>
            <div class="flex-1 bg-white rounded-lg shadow-sm p-4 max-w-3xl">
                <div class="text-gray-700 text-sm whitespace-pre-wrap">${escapeHtml(content)}</div>
            </div>
        `;
    }
    div.appendChild(msg);
    div.scrollTop = div.scrollHeight;
}

function showTypingIndicator() {
    const div = document.getElementById('chatMessages');
    const ind = document.createElement('div');
    ind.id = 'typingIndicator';
    ind.className = 'message flex gap-3';
    ind.innerHTML = `
        <div class="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-white flex-shrink-0"></div>
        <div class="bg-white rounded-lg shadow-sm p-4">
            <div class="typing-indicator flex gap-1">
                <span class="w-2 h-2 bg-gray-400 rounded-full"></span>
                <span class="w-2 h-2 bg-gray-400 rounded-full"></span>
                <span class="w-2 h-2 bg-gray-400 rounded-full"></span>
            </div>
        </div>
    `;
    div.appendChild(ind);
    div.scrollTop = div.scrollHeight;
}

function hideTypingIndicator() {
    const ind = document.getElementById('typingIndicator');
    if (ind) ind.remove();
}

function switchTab(tab) {
    ['todos', 'files', 'calendar'].forEach(t => {
        document.getElementById(`${t}Panel`).classList.toggle('hidden', t !== tab);
        const tabBtn = document.getElementById(`${t}Tab`);
        if (t === tab) {
            tabBtn.classList.add('text-blue-600', 'border-b-2', 'border-blue-600');
            tabBtn.classList.remove('text-gray-600');
        } else {
            tabBtn.classList.remove('text-blue-600', 'border-b-2', 'border-blue-600');
            tabBtn.classList.add('text-gray-600');
        }
    });
}

function updateTodosList() {
    const list = document.getElementById('todosList');
    if (!state || !state.todos || state.todos.length === 0) {
        list.innerHTML = '<div class="text-sm text-gray-400 italic">No tasks yet</div>';
        return;
    }
    list.innerHTML = state.todos.map(todo => `
        <div class="p-3 rounded-lg border ${todo.completed ? 'bg-green-50 border-green-200' : 'bg-gray-50 border-gray-200'}">
            <div class="flex gap-2">
                <span>${todo.completed ? 'Completed' : 'Pending'}</span>
                <div class="flex-1">
                    <div class="text-sm font-medium ${todo.completed ? 'line-through text-gray-500' : 'text-gray-700'}">
                        ${escapeHtml(todo.title)}
                    </div>
                    ${todo.priority ? `<div class="text-xs text-gray-500">Priority: ${todo.priority}</div>` : ''}
                    ${todo.due_date ? `<div class="text-xs text-gray-500">Due: ${todo.due_date}</div>` : ''}
                </div>
            </div>
        </div>
    `).join('');
}

function updateFilesList() {
    const list = document.getElementById('filesList');
    if (!state || !state.files || Object.keys(state.files).length === 0) {
        list.innerHTML = '<div class="text-sm text-gray-400 italic">No files yet</div>';
        return;
    }
    list.innerHTML = Object.keys(state.files).map(filename => `
        <div class="p-3 rounded-lg border border-gray-200 cursor-pointer hover:bg-gray-50" onclick="viewFile('${filename}')">
            <div class="flex items-center gap-2">
                <span>File</span>
                <div class="flex-1">
                    <div class="text-sm font-medium">${escapeHtml(filename)}</div>
                    <div class="text-xs text-gray-500">${state.files[filename].length} chars</div>
                </div>
                <span class="text-gray-400">View</span>
            </div>
        </div>
    `).join('');
}

function updateCalendarList() {
    const list = document.getElementById('calendarList');
    if (!state || !state.calendar || state.calendar.length === 0) {
        list.innerHTML = '<div class="text-sm text-gray-400 italic">No events yet</div>';
        return;
    }
    list.innerHTML = state.calendar.map(event => `
        <div class="p-3 rounded-lg border border-blue-200 bg-blue-50">
            <div class="flex gap-3">
                <span class="text-2xl">Event</span>
                <div class="flex-1">
                    <div class="font-medium">${escapeHtml(event.title)}</div>
                    <div class="text-sm text-gray-600 mt-1">Date ${event.date} at ${event.time}</div>
                    ${event.description ? `<div class="text-xs text-gray-500 mt-2">${escapeHtml(event.description)}</div>` : ''}
                    ${event.attendees && event.attendees.length > 0 ? `<div class="text-xs text-gray-500">Attendees: ${event.attendees.join(', ')}</div>` : ''}
                </div>
            </div>
        </div>
    `).join('');
}

function updateStats() {
    document.getElementById('todoCount').textContent = state?.todos?.length || 0;
    document.getElementById('fileCount').textContent = state?.files ? Object.keys(state.files).length : 0;
    document.getElementById('eventCount').textContent = state?.calendar?.length || 0;
}

function viewFile(filename) {
    document.getElementById('modalFileName').textContent = filename;
    document.getElementById('modalFileContent').textContent = state.files[filename];
    document.getElementById('fileModal').classList.remove('hidden');
}

function closeFileModal() {
    document.getElementById('fileModal').classList.add('hidden');
}

function clearChat() {
    if (confirm('Clear chat? (State will be preserved)')) {
        document.getElementById('chatMessages').innerHTML = '';
        addMessage('assistant', 'Chat cleared. How can I help?');
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}