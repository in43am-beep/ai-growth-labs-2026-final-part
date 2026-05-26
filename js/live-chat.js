/**
 * Live Chat Widget — AI Growth Labs
 * Custom chatbot with SEO expertise
 */
(function() {
  'use strict';

  const API_URL = window.VOICE_API_URL || window.location.origin;
  let sessionId = null;
  let chatHistory = [];
  let isActive = false;

  const style = document.createElement('style');
  style.textContent = `
    .lc-widget {
      position: fixed;
      bottom: 220px;
      right: 24px;
      z-index: 10002;
      width: 380px;
      max-height: 520px;
      background: #0F1629;
      border: 1px solid rgba(102,126,234,0.3);
      border-radius: 16px;
      box-shadow: 0 20px 60px rgba(0,0,0,0.5);
      display: none;
      flex-direction: column;
      overflow: hidden;
      font-family: 'Inter', sans-serif;
    }
    .lc-widget.active { display: flex; }

    .lc-header {
      background: linear-gradient(135deg, rgba(102,126,234,0.2), rgba(118,75,162,0.2));
      padding: 14px 18px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      border-bottom: 1px solid rgba(255,255,255,0.08);
    }
    .lc-header-info {
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .lc-avatar {
      width: 36px;
      height: 36px;
      border-radius: 50%;
      background: linear-gradient(135deg, #667eea, #764ba2);
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .lc-avatar svg { width: 18px; height: 18px; fill: white; }
    .lc-header h4 { color: white; margin: 0; font-size: 14px; font-weight: 600; }
    .lc-header p { color: #667eea; margin: 0; font-size: 11px; }
    .lc-close {
      background: none; border: none;
      color: rgba(255,255,255,0.5);
      font-size: 20px; cursor: pointer;
      padding: 4px 8px; border-radius: 6px;
      transition: all 0.2s;
    }
    .lc-close:hover { color: white; background: rgba(255,255,255,0.1); }

    .lc-intro {
      padding: 18px;
      display: flex;
      flex-direction: column;
      gap: 10px;
    }
    .lc-intro h3 { color: white; margin: 0; font-size: 15px; }
    .lc-intro p { color: rgba(255,255,255,0.5); margin: 0; font-size: 12px; line-height: 1.5; }
    .lc-intro-input {
      background: rgba(255,255,255,0.06);
      border: 1px solid rgba(255,255,255,0.12);
      border-radius: 8px;
      padding: 10px 12px;
      color: white;
      font-size: 13px;
      font-family: 'Inter', sans-serif;
      outline: none;
    }
    .lc-intro-input:focus { border-color: #667eea; }
    .lc-intro-input::placeholder { color: rgba(255,255,255,0.3); }
    .lc-start-btn {
      background: linear-gradient(135deg, #667eea, #764ba2);
      border: none; color: white;
      font-size: 13px; font-weight: 600;
      padding: 10px; border-radius: 8px;
      cursor: pointer; font-family: 'Inter', sans-serif;
      transition: transform 0.2s;
    }
    .lc-start-btn:hover { transform: scale(1.02); }
    .lc-start-btn:disabled { opacity: 0.5; cursor: not-allowed; }

    .lc-messages {
      flex: 1;
      overflow-y: auto;
      padding: 14px;
      display: flex;
      flex-direction: column;
      gap: 10px;
      max-height: 310px;
    }
    .lc-messages::-webkit-scrollbar { width: 4px; }
    .lc-messages::-webkit-scrollbar-thumb { background: rgba(102,126,234,0.3); border-radius: 4px; }

    .lc-msg {
      max-width: 85%;
      padding: 10px 13px;
      border-radius: 12px;
      font-size: 13px;
      line-height: 1.5;
      color: white;
      animation: lc-fadein 0.3s ease;
    }
    .lc-msg.assistant {
      align-self: flex-start;
      background: rgba(102,126,234,0.15);
      border: 1px solid rgba(102,126,234,0.25);
      border-bottom-left-radius: 4px;
    }
    .lc-msg.user {
      align-self: flex-end;
      background: rgba(118,75,162,0.2);
      border: 1px solid rgba(118,75,162,0.3);
      border-bottom-right-radius: 4px;
    }
    .lc-msg.system {
      align-self: center;
      background: rgba(255,255,255,0.05);
      color: rgba(255,255,255,0.5);
      font-size: 11px;
      text-align: center;
    }
    @keyframes lc-fadein {
      from { opacity: 0; transform: translateY(6px); }
      to { opacity: 1; transform: translateY(0); }
    }

    .lc-typing {
      display: none;
      align-self: flex-start;
      padding: 10px 14px;
      background: rgba(102,126,234,0.15);
      border: 1px solid rgba(102,126,234,0.25);
      border-radius: 12px;
      border-bottom-left-radius: 4px;
    }
    .lc-typing.show { display: flex; gap: 4px; }
    .lc-typing span {
      width: 6px; height: 6px; border-radius: 50%;
      background: #667eea; animation: lc-bounce 1.4s infinite;
    }
    .lc-typing span:nth-child(2) { animation-delay: 0.2s; }
    .lc-typing span:nth-child(3) { animation-delay: 0.4s; }
    @keyframes lc-bounce {
      0%, 80%, 100% { transform: scale(0); opacity: 0.5; }
      40% { transform: scale(1); opacity: 1; }
    }

    .lc-input-area {
      padding: 10px 14px;
      border-top: 1px solid rgba(255,255,255,0.08);
      display: flex;
      gap: 8px;
    }
    .lc-input {
      flex: 1;
      background: rgba(255,255,255,0.06);
      border: 1px solid rgba(255,255,255,0.12);
      border-radius: 8px;
      padding: 9px 12px;
      color: white;
      font-size: 13px;
      font-family: 'Inter', sans-serif;
      outline: none;
    }
    .lc-input:focus { border-color: #667eea; }
    .lc-input::placeholder { color: rgba(255,255,255,0.3); }
    .lc-send {
      width: 38px; height: 38px;
      border-radius: 8px;
      background: linear-gradient(135deg, #667eea, #764ba2);
      border: none; cursor: pointer;
      display: flex; align-items: center; justify-content: center;
      transition: transform 0.2s;
    }
    .lc-send:hover { transform: scale(1.05); }
    .lc-send:disabled { opacity: 0.4; cursor: not-allowed; }
    .lc-send svg { width: 16px; height: 16px; fill: white; }

    .lc-online-dot {
      width: 8px; height: 8px;
      border-radius: 50%;
      background: #00FF88;
      display: inline-block;
      margin-right: 4px;
      animation: lc-pulse 2s infinite;
    }
    @keyframes lc-pulse {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.4; }
    }

    @media (max-width: 480px) {
      .lc-widget {
        width: calc(100vw - 24px);
        right: 12px;
        bottom: 200px;
        max-height: 400px;
      }
    }
  `;
  document.head.appendChild(style);

  // Create widget
  const widget = document.createElement('div');
  widget.className = 'lc-widget';
  widget.id = 'lcWidget';
  widget.innerHTML = `
    <div class="lc-header">
      <div class="lc-header-info">
        <div class="lc-avatar">
          <svg viewBox="0 0 24 24"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H5.17L4 17.17V4h16v12z"/></svg>
        </div>
        <div>
          <h4>Growth Consultant</h4>
          <p id="lcStatus"><span class="lc-online-dot"></span>Online</p>
        </div>
      </div>
      <button class="lc-close" id="lcClose">&times;</button>
    </div>
    <div id="lcIntro" class="lc-intro">
      <h3>Chat with Our Team</h3>
      <p>Get expert advice on SEO, digital marketing, and growing your online presence. No obligation!</p>
      <input class="lc-intro-input" id="lcName" placeholder="Your Name (optional)">
      <input class="lc-intro-input" id="lcEmail" placeholder="Email (optional)" type="email">
      <button class="lc-start-btn" id="lcStartBtn">Start Chat</button>
    </div>
    <div id="lcChatArea" style="display:none;flex:1;flex-direction:column;">
      <div class="lc-messages" id="lcMessages"></div>
      <div class="lc-typing" id="lcTyping"><span></span><span></span><span></span></div>
      <div class="lc-input-area">
        <input class="lc-input" id="lcInput" placeholder="Type a message..." maxlength="500">
        <button class="lc-send" id="lcSend">
          <svg viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>
        </button>
      </div>
    </div>
  `;
  document.body.appendChild(widget);

  // Wire up the Live Chat FAB button
  const fabLiveChat = document.querySelector('.fab-livechat');
  if (fabLiveChat) {
    fabLiveChat.removeAttribute('onclick');
    fabLiveChat.addEventListener('click', function(e) {
      e.preventDefault();
      widget.classList.toggle('active');
    });
  }

  document.getElementById('lcClose').addEventListener('click', function() {
    widget.classList.remove('active');
  });
  document.getElementById('lcStartBtn').addEventListener('click', startChat);
  document.getElementById('lcSend').addEventListener('click', sendMsg);
  document.getElementById('lcInput').addEventListener('keypress', function(e) {
    if (e.key === 'Enter') sendMsg();
  });

  async function startChat() {
    const name = document.getElementById('lcName').value.trim();
    const email = document.getElementById('lcEmail').value.trim();

    const btn = document.getElementById('lcStartBtn');
    btn.disabled = true;
    btn.textContent = 'Connecting...';

    try {
      const resp = await fetch(API_URL + '/api/chat/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, email })
      });
      const data = await resp.json();
      sessionId = data.session_id;
      isActive = true;
      chatHistory = [];

      document.getElementById('lcIntro').style.display = 'none';
      const chatArea = document.getElementById('lcChatArea');
      chatArea.style.display = 'flex';
      chatArea.style.flexDirection = 'column';
      chatArea.style.flex = '1';

      addMsg('assistant', data.message);
    } catch (err) {
      btn.disabled = false;
      btn.textContent = 'Start Chat';
      alert('Connection error. Please try again.');
    }
  }

  async function sendMsg() {
    const input = document.getElementById('lcInput');
    const msg = input.value.trim();
    if (!msg || !isActive) return;

    input.value = '';
    addMsg('user', msg);

    document.getElementById('lcSend').disabled = true;
    document.getElementById('lcTyping').classList.add('show');

    try {
      const resp = await fetch(API_URL + '/api/chat/message', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, message: msg, history: chatHistory })
      });
      const data = await resp.json();
      addMsg('assistant', data.response);
    } catch (err) {
      addMsg('system', 'Error. Please try again.');
    }

    document.getElementById('lcSend').disabled = false;
    document.getElementById('lcTyping').classList.remove('show');
    input.focus();
  }

  function addMsg(role, content) {
    const container = document.getElementById('lcMessages');
    const div = document.createElement('div');
    div.className = 'lc-msg ' + role;
    div.textContent = content;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
    if (role !== 'system') {
      chatHistory.push({ role, content });
    }
  }

  // Expose toggle for external use
  window.toggleLiveChat = function() {
    widget.classList.toggle('active');
  };
})();
