/**
 * Dashboard Notification Bell System
 */
(function() {
  'use strict';

  // Inject styles
  const style = document.createElement('style');
  style.textContent = `
    .notif-bell {
      position: relative;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 40px;
      height: 40px;
      border-radius: 8px;
      background: rgba(255,255,255,0.06);
      border: 1px solid rgba(255,255,255,0.1);
      cursor: pointer;
      transition: all 0.2s;
      margin-right: 8px;
    }
    .notif-bell:hover { background: rgba(255,255,255,0.1); }
    .notif-bell svg { width: 20px; height: 20px; fill: rgba(255,255,255,0.7); }
    .notif-badge {
      position: absolute;
      top: -4px;
      right: -4px;
      background: #ff4444;
      color: white;
      font-size: 10px;
      font-weight: 700;
      min-width: 18px;
      height: 18px;
      line-height: 18px;
      text-align: center;
      border-radius: 9px;
      font-family: 'Inter', sans-serif;
      display: none;
      padding: 0 4px;
    }
    .notif-badge.show { display: block; }

    .notif-dropdown {
      position: absolute;
      top: 48px;
      right: 0;
      width: 360px;
      max-height: 420px;
      background: #0F172A;
      border: 1px solid rgba(255,255,255,0.1);
      border-radius: 12px;
      box-shadow: 0 16px 48px rgba(0,0,0,0.5);
      z-index: 9999;
      display: none;
      overflow: hidden;
      font-family: 'Inter', sans-serif;
    }
    .notif-dropdown.open { display: block; }
    .notif-dropdown-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 14px 16px;
      border-bottom: 1px solid rgba(255,255,255,0.08);
    }
    .notif-dropdown-header h4 {
      font-size: 14px;
      font-weight: 600;
      color: white;
      margin: 0;
    }
    .notif-mark-all {
      font-size: 11px;
      color: #00D4FF;
      cursor: pointer;
      background: none;
      border: none;
      font-family: 'Inter', sans-serif;
    }
    .notif-mark-all:hover { text-decoration: underline; }

    .notif-list {
      max-height: 350px;
      overflow-y: auto;
    }
    .notif-list::-webkit-scrollbar { width: 4px; }
    .notif-list::-webkit-scrollbar-thumb { background: rgba(0,212,255,0.2); border-radius: 4px; }

    .notif-item {
      padding: 12px 16px;
      border-bottom: 1px solid rgba(255,255,255,0.04);
      cursor: pointer;
      transition: background 0.2s;
    }
    .notif-item:hover { background: rgba(255,255,255,0.04); }
    .notif-item.unread { background: rgba(0,212,255,0.04); border-left: 3px solid #00D4FF; }
    .notif-item-title {
      font-size: 13px;
      font-weight: 500;
      color: white;
      margin-bottom: 4px;
    }
    .notif-item-msg {
      font-size: 11px;
      color: rgba(255,255,255,0.5);
      line-height: 1.4;
    }
    .notif-item-time {
      font-size: 10px;
      color: rgba(255,255,255,0.3);
      margin-top: 4px;
    }
    .notif-empty {
      padding: 30px;
      text-align: center;
      color: rgba(255,255,255,0.4);
      font-size: 13px;
    }
  `;
  document.head.appendChild(style);

  // Insert bell into header-actions
  const headerActions = document.querySelector('.header-actions');
  if (!headerActions) return;

  const bellContainer = document.createElement('div');
  bellContainer.style.cssText = 'position:relative;display:inline-block;';
  bellContainer.innerHTML = `
    <div class="notif-bell" id="notifBell">
      <svg viewBox="0 0 24 24"><path d="M12 22c1.1 0 2-.9 2-2h-4c0 1.1.9 2 2 2zm6-6v-5c0-3.07-1.63-5.64-4.5-6.32V4c0-.83-.67-1.5-1.5-1.5s-1.5.67-1.5 1.5v.68C7.64 5.36 6 7.92 6 11v5l-2 2v1h16v-1l-2-2z"/></svg>
      <span class="notif-badge" id="notifBadge">0</span>
    </div>
    <div class="notif-dropdown" id="notifDropdown">
      <div class="notif-dropdown-header">
        <h4>Notifications</h4>
        <button class="notif-mark-all" id="notifMarkAll">Mark all read</button>
      </div>
      <div class="notif-list" id="notifList">
        <div class="notif-empty">No notifications</div>
      </div>
    </div>
  `;
  headerActions.insertBefore(bellContainer, headerActions.firstChild);

  // Toggle dropdown
  document.getElementById('notifBell').addEventListener('click', function(e) {
    e.stopPropagation();
    document.getElementById('notifDropdown').classList.toggle('open');
    loadNotifications();
  });

  document.addEventListener('click', function() {
    document.getElementById('notifDropdown').classList.remove('open');
  });

  document.getElementById('notifMarkAll').addEventListener('click', async function(e) {
    e.stopPropagation();
    try {
      await fetch('/api/notifications/read-all', { method: 'POST', credentials: 'same-origin' });
      loadNotifications();
    } catch (err) {}
  });

  function timeAgo(dateStr) {
    const now = new Date();
    const d = new Date(dateStr + 'Z');
    const diff = Math.floor((now - d) / 1000);
    if (diff < 60) return 'Just now';
    if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
    if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
    return Math.floor(diff / 86400) + 'd ago';
  }

  async function loadNotifications() {
    try {
      const resp = await fetch('/api/notifications', { credentials: 'same-origin' });
      const data = await resp.json();

      const badge = document.getElementById('notifBadge');
      if (data.unread_count > 0) {
        badge.textContent = data.unread_count > 99 ? '99+' : data.unread_count;
        badge.classList.add('show');
      } else {
        badge.classList.remove('show');
      }

      const list = document.getElementById('notifList');
      if (!data.notifications || data.notifications.length === 0) {
        list.innerHTML = '<div class="notif-empty">No notifications yet</div>';
        return;
      }

      list.innerHTML = data.notifications.map(n => `
        <div class="notif-item ${n.is_read ? '' : 'unread'}" data-id="${n.id}" onclick="markNotifRead(${n.id}, '${n.link || ''}')">
          <div class="notif-item-title">${escapeHtml(n.title)}</div>
          <div class="notif-item-msg">${escapeHtml(n.message || '')}</div>
          <div class="notif-item-time">${timeAgo(n.created_at)}</div>
        </div>
      `).join('');
    } catch (err) {}
  }

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  window.markNotifRead = async function(id, link) {
    try {
      await fetch('/api/notifications/' + id + '/read', { method: 'POST', credentials: 'same-origin' });
    } catch (err) {}
    if (link) window.location.href = link;
    loadNotifications();
  };

  // Initial load
  loadNotifications();
  // Poll every 30 seconds
  setInterval(loadNotifications, 30000);
})();
