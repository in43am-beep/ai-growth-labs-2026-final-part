/**
 * AI Voice Call Widget — AI Growth Labs
 * Floating call button + chat interface powered by Gemini AI
 */
(function() {
  'use strict';

  const API_URL = window.VOICE_API_URL || window.location.origin;

  let callId = null;
  let chatHistory = [];
  let isCallActive = false;

  // Inject CSS
  const style = document.createElement('style');
  style.textContent = `
    .voice-call-btn {
      position: fixed;
      bottom: 90px;
      right: 28px;
      z-index: 10000;
      width: 60px;
      height: 60px;
      border-radius: 50%;
      background: linear-gradient(135deg, #00D4FF 0%, #7B2FFF 100%);
      border: none;
      cursor: pointer;
      box-shadow: 0 4px 20px rgba(0, 212, 255, 0.4);
      display: flex;
      align-items: center;
      justify-content: center;
      transition: transform 0.3s, box-shadow 0.3s;
      animation: voice-pulse 2s infinite;
    }
    .voice-call-btn:hover {
      transform: scale(1.1);
      box-shadow: 0 6px 30px rgba(0, 212, 255, 0.6);
    }
    .voice-call-btn svg {
      width: 28px;
      height: 28px;
      fill: white;
    }
    .voice-call-btn .badge {
      position: absolute;
      top: -2px;
      right: -2px;
      background: #ff4444;
      color: white;
      font-size: 10px;
      font-weight: 700;
      padding: 2px 6px;
      border-radius: 10px;
      font-family: 'Inter', sans-serif;
    }
    @keyframes voice-pulse {
      0%, 100% { box-shadow: 0 4px 20px rgba(0, 212, 255, 0.4); }
      50% { box-shadow: 0 4px 30px rgba(123, 47, 255, 0.6); }
    }

    .voice-call-widget {
      position: fixed;
      bottom: 160px;
      right: 28px;
      z-index: 10001;
      width: 380px;
      max-height: 520px;
      background: #0F1629;
      border: 1px solid rgba(0, 212, 255, 0.2);
      border-radius: 16px;
      box-shadow: 0 20px 60px rgba(0,0,0,0.5);
      display: none;
      flex-direction: column;
      overflow: hidden;
      font-family: 'Inter', sans-serif;
    }
    .voice-call-widget.active { display: flex; }

    .vcw-header {
      background: linear-gradient(135deg, rgba(0,212,255,0.15), rgba(123,47,255,0.15));
      padding: 16px 20px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      border-bottom: 1px solid rgba(255,255,255,0.08);
    }
    .vcw-header-info {
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .vcw-avatar {
      width: 40px;
      height: 40px;
      border-radius: 50%;
      background: linear-gradient(135deg, #00D4FF, #7B2FFF);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 18px;
    }
    .vcw-header h4 {
      color: white;
      margin: 0;
      font-size: 15px;
      font-weight: 600;
    }
    .vcw-header p {
      color: #00D4FF;
      margin: 0;
      font-size: 12px;
    }
    .vcw-close {
      background: none;
      border: none;
      color: rgba(255,255,255,0.5);
      font-size: 22px;
      cursor: pointer;
      padding: 4px 8px;
      border-radius: 6px;
      transition: all 0.2s;
    }
    .vcw-close:hover { color: white; background: rgba(255,255,255,0.1); }

    .vcw-messages {
      flex: 1;
      overflow-y: auto;
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 12px;
      max-height: 300px;
    }
    .vcw-messages::-webkit-scrollbar { width: 4px; }
    .vcw-messages::-webkit-scrollbar-thumb { background: rgba(0,212,255,0.3); border-radius: 4px; }

    .vcw-msg {
      max-width: 85%;
      padding: 10px 14px;
      border-radius: 12px;
      font-size: 13px;
      line-height: 1.5;
      color: white;
      animation: vcw-fadein 0.3s ease;
    }
    .vcw-msg.assistant {
      align-self: flex-start;
      background: rgba(0,212,255,0.12);
      border: 1px solid rgba(0,212,255,0.2);
      border-bottom-left-radius: 4px;
    }
    .vcw-msg.user {
      align-self: flex-end;
      background: rgba(123,47,255,0.2);
      border: 1px solid rgba(123,47,255,0.3);
      border-bottom-right-radius: 4px;
    }
    .vcw-msg.system {
      align-self: center;
      background: rgba(255,255,255,0.05);
      color: rgba(255,255,255,0.5);
      font-size: 12px;
      text-align: center;
    }
    @keyframes vcw-fadein {
      from { opacity: 0; transform: translateY(8px); }
      to { opacity: 1; transform: translateY(0); }
    }

    .vcw-typing {
      display: none;
      align-self: flex-start;
      padding: 10px 14px;
      background: rgba(0,212,255,0.12);
      border: 1px solid rgba(0,212,255,0.2);
      border-radius: 12px;
      border-bottom-left-radius: 4px;
    }
    .vcw-typing.show { display: flex; gap: 4px; }
    .vcw-typing span {
      width: 6px; height: 6px; border-radius: 50%;
      background: #00D4FF; animation: vcw-bounce 1.4s infinite;
    }
    .vcw-typing span:nth-child(2) { animation-delay: 0.2s; }
    .vcw-typing span:nth-child(3) { animation-delay: 0.4s; }
    @keyframes vcw-bounce {
      0%, 80%, 100% { transform: scale(0); opacity: 0.5; }
      40% { transform: scale(1); opacity: 1; }
    }

    .vcw-input-area {
      padding: 12px 16px;
      border-top: 1px solid rgba(255,255,255,0.08);
      display: flex;
      gap: 8px;
    }
    .vcw-input {
      flex: 1;
      background: rgba(255,255,255,0.06);
      border: 1px solid rgba(255,255,255,0.12);
      border-radius: 10px;
      padding: 10px 14px;
      color: white;
      font-size: 13px;
      font-family: 'Inter', sans-serif;
      outline: none;
      transition: border-color 0.2s;
    }
    .vcw-input:focus { border-color: #00D4FF; }
    .vcw-input::placeholder { color: rgba(255,255,255,0.3); }
    .vcw-send {
      width: 40px; height: 40px;
      border-radius: 10px;
      background: linear-gradient(135deg, #00D4FF, #7B2FFF);
      border: none;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: transform 0.2s;
    }
    .vcw-send:hover { transform: scale(1.05); }
    .vcw-send:disabled { opacity: 0.4; cursor: not-allowed; }
    .vcw-send svg { width: 18px; height: 18px; fill: white; }

    .vcw-footer {
      padding: 8px 16px;
      text-align: center;
      border-top: 1px solid rgba(255,255,255,0.05);
    }
    .vcw-end-call {
      background: rgba(255,68,68,0.15);
      border: 1px solid rgba(255,68,68,0.3);
      color: #ff6666;
      font-size: 12px;
      font-weight: 600;
      padding: 6px 16px;
      border-radius: 8px;
      cursor: pointer;
      font-family: 'Inter', sans-serif;
      transition: all 0.2s;
    }
    .vcw-end-call:hover { background: rgba(255,68,68,0.25); color: #ff4444; }

    .vcw-start-form {
      padding: 20px;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }
    .vcw-start-form h3 {
      color: white;
      margin: 0 0 4px;
      font-size: 16px;
    }
    .vcw-start-form p {
      color: rgba(255,255,255,0.5);
      margin: 0 0 8px;
      font-size: 13px;
    }
    .vcw-form-input {
      background: rgba(255,255,255,0.06);
      border: 1px solid rgba(255,255,255,0.12);
      border-radius: 8px;
      padding: 10px 12px;
      color: white;
      font-size: 13px;
      font-family: 'Inter', sans-serif;
      outline: none;
    }
    .vcw-form-input:focus { border-color: #00D4FF; }
    .vcw-form-input::placeholder { color: rgba(255,255,255,0.3); }
    .vcw-start-btn {
      background: linear-gradient(135deg, #00D4FF, #7B2FFF);
      border: none;
      color: white;
      font-size: 14px;
      font-weight: 600;
      padding: 12px;
      border-radius: 10px;
      cursor: pointer;
      font-family: 'Inter', sans-serif;
      transition: transform 0.2s;
      margin-top: 4px;
    }
    .vcw-start-btn:hover { transform: scale(1.02); }
    .vcw-start-btn:disabled { opacity: 0.5; cursor: not-allowed; }

    @media (max-width: 480px) {
      .voice-call-widget {
        width: calc(100vw - 24px);
        right: 12px;
        bottom: 140px;
        max-height: 440px;
      }
    }
  `;
  document.head.appendChild(style);

  // Create floating button
  const btn = document.createElement('button');
  btn.className = 'voice-call-btn';
  btn.title = 'Talk to AI Sales Agent';
  btn.innerHTML = `
    <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
      <path d="M20.01 15.38c-1.23 0-2.42-.2-3.53-.56a.977.977 0 00-1.01.24l-1.57 1.97c-2.83-1.35-5.48-3.9-6.89-6.83l1.95-1.66c.27-.28.35-.67.24-1.02-.37-1.11-.56-2.3-.56-3.53 0-.54-.45-.99-.99-.99H4.19C3.65 3 3 3.24 3 3.99 3 13.28 10.73 21 20.01 21c.71 0 .99-.63.99-1.18v-3.45c0-.54-.45-.99-.99-.99z"/>
    </svg>
    <span class="badge">AI</span>
  `;
  btn.addEventListener('click', toggleWidget);
  document.body.appendChild(btn);

  // Create widget
  const widget = document.createElement('div');
  widget.className = 'voice-call-widget';
  widget.innerHTML = `
    <div class="vcw-header">
      <div class="vcw-header-info">
        <div class="vcw-avatar">&#x1F4DE;</div>
        <div>
          <h4>AI Sales Agent</h4>
          <p id="vcwStatus">Ready to connect</p>
        </div>
      </div>
      <button class="vcw-close" id="vcwClose">&times;</button>
    </div>
    <div id="vcwStartForm" class="vcw-start-form">
      <h3>Start AI Consultation</h3>
      <p>Our AI agent Sarah will help you find the right SEO solution for your business.</p>
      <input class="vcw-form-input" id="vcwName" placeholder="Your Name *" required>
      <input class="vcw-form-input" id="vcwEmail" placeholder="Email *" type="email" required>
      <input class="vcw-form-input" id="vcwPhone" placeholder="Phone (optional)" type="tel">
      <input class="vcw-form-input" id="vcwBusiness" placeholder="Business Name (optional)">
      <button class="vcw-start-btn" id="vcwStartBtn">Start AI Call &#x1F4DE;</button>
    </div>
    <div id="vcwChat" style="display:none;flex:1;display:none;flex-direction:column;">
      <div class="vcw-messages" id="vcwMessages"></div>
      <div class="vcw-typing" id="vcwTyping"><span></span><span></span><span></span></div>
      <div class="vcw-input-area">
        <input class="vcw-input" id="vcwInput" placeholder="Type your message..." maxlength="500">
        <button class="vcw-send" id="vcwSend">
          <svg viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>
        </button>
      </div>
      <div class="vcw-footer">
        <button class="vcw-end-call" id="vcwEndCall">End Call</button>
      </div>
    </div>
  `;
  document.body.appendChild(widget);

  // Event listeners
  document.getElementById('vcwClose').addEventListener('click', toggleWidget);
  document.getElementById('vcwStartBtn').addEventListener('click', startCall);
  document.getElementById('vcwSend').addEventListener('click', sendMessage);
  document.getElementById('vcwInput').addEventListener('keypress', function(e) {
    if (e.key === 'Enter') sendMessage();
  });
  document.getElementById('vcwEndCall').addEventListener('click', endCall);

  function toggleWidget() {
    widget.classList.toggle('active');
  }

  async function startCall() {
    const name = document.getElementById('vcwName').value.trim();
    const email = document.getElementById('vcwEmail').value.trim();
    const phone = document.getElementById('vcwPhone').value.trim();
    const business = document.getElementById('vcwBusiness').value.trim();

    if (!name || !email) {
      alert('Please enter your name and email.');
      return;
    }

    const startBtn = document.getElementById('vcwStartBtn');
    startBtn.disabled = true;
    startBtn.textContent = 'Connecting...';

    try {
      const resp = await fetch(API_URL + '/api/voice/call/initiate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, email, phone, business_name: business, service: '' })
      });
      const data = await resp.json();
      callId = data.call_id;
      isCallActive = true;
      chatHistory = data.transcript || [];

      // Switch to chat view
      document.getElementById('vcwStartForm').style.display = 'none';
      const chatEl = document.getElementById('vcwChat');
      chatEl.style.display = 'flex';
      chatEl.style.flexDirection = 'column';
      chatEl.style.flex = '1';
      document.getElementById('vcwStatus').textContent = 'Connected with Sarah';
      document.getElementById('vcwStatus').style.color = '#00FF88';

      // Show greeting
      addMessage('assistant', data.message);

    } catch (err) {
      startBtn.disabled = false;
      startBtn.textContent = 'Start AI Call \u{1F4DE}';
      addMessage('system', 'Connection failed. Please try again or call us at +1-800-971-0199.');
    }
  }

  async function sendMessage() {
    const input = document.getElementById('vcwInput');
    const msg = input.value.trim();
    if (!msg || !isCallActive) return;

    input.value = '';
    addMessage('user', msg);

    const sendBtn = document.getElementById('vcwSend');
    sendBtn.disabled = true;
    document.getElementById('vcwTyping').classList.add('show');

    try {
      const resp = await fetch(API_URL + '/api/voice/call/' + callId + '/message', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: msg, history: chatHistory })
      });
      const data = await resp.json();
      chatHistory = data.transcript || chatHistory;
      addMessage('assistant', data.response);
    } catch (err) {
      addMessage('system', 'Error sending message. Please try again.');
    }

    sendBtn.disabled = false;
    document.getElementById('vcwTyping').classList.remove('show');
    input.focus();
  }

  async function endCall() {
    if (!callId) return;
    isCallActive = false;

    try {
      const resp = await fetch(API_URL + '/api/voice/call/' + callId + '/end', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      const data = await resp.json();
      addMessage('system', data.message || 'Call ended. Thank you!');
      if (data.summary) {
        addMessage('system', 'Summary: ' + data.summary);
      }
    } catch (err) {
      addMessage('system', 'Call ended.');
    }

    document.getElementById('vcwStatus').textContent = 'Call ended';
    document.getElementById('vcwStatus').style.color = '#ff6666';
    document.getElementById('vcwInput').disabled = true;
    document.getElementById('vcwSend').disabled = true;
    document.getElementById('vcwEndCall').textContent = 'Call Ended';
    document.getElementById('vcwEndCall').disabled = true;
  }

  function addMessage(role, content) {
    const container = document.getElementById('vcwMessages');
    const div = document.createElement('div');
    div.className = 'vcw-msg ' + role;
    div.textContent = content;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;

    if (role !== 'system') {
      chatHistory.push({ role, content });
    }
  }
})();
