/* RankForge AI — front-end auth (signup/login/dashboard) */
(function (window) {
  'use strict';

  var TOKEN_KEY = 'rf_token';
  var API = (typeof window !== 'undefined' && window.API_BASE) ? window.API_BASE : ''; // backend base URL

  function getToken() { return localStorage.getItem(TOKEN_KEY); }
  function setToken(t) { localStorage.setItem(TOKEN_KEY, t); }
  function clearToken() { localStorage.removeItem(TOKEN_KEY); }

  function showAlert(msg, type) {
    var el = document.getElementById('form-alert');
    if (!el) { alert(msg); return; }
    el.textContent = msg;
    el.style.display = 'block';
    el.className = (type === 'success' ? 'success-message' : 'error-message');
  }

  function fieldError(name, msg) {
    var input = document.getElementById(name);
    var span = document.querySelector('.error-message[data-for="' + name + '"]');
    if (input) input.classList.toggle('field-error', !!msg);
    if (span) span.textContent = msg || '';
  }

  function clearErrors(form) {
    form.querySelectorAll('.field-error').forEach(function (i) { i.classList.remove('field-error'); });
    form.querySelectorAll('.error-message[data-for]').forEach(function (s) { s.textContent = ''; });
    var alertEl = document.getElementById('form-alert');
    if (alertEl) alertEl.style.display = 'none';
  }

  function validEmail(v) { return /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(v); }

  function api(path, method, body) {
    var headers = { 'Content-Type': 'application/json' };
    var t = getToken();
    if (t) headers['Authorization'] = 'Bearer ' + t;
    return fetch(API + path, {
      method: method || 'GET',
      headers: headers,
      body: body ? JSON.stringify(body) : undefined
    }).then(function (r) {
      return r.json().then(function (data) { return { ok: r.ok, status: r.status, data: data }; });
    });
  }

  function bindPasswordToggles() {
    document.querySelectorAll('.pw-toggle').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var input = document.getElementById(btn.dataset.target);
        if (!input) return;
        var show = input.type === 'password';
        input.type = show ? 'text' : 'password';
        btn.textContent = show ? 'Hide' : 'Show';
      });
    });
  }

  function bindGoogle() {
    var g = document.getElementById('google-btn');
    if (!g) return;
    g.addEventListener('click', function () {
      g.disabled = true;
      // Check whether Google OAuth is configured on the backend before redirecting.
      api('/api/integrations/status').then(function (res) {
        if (res.ok && res.data && res.data.google_oauth) {
          window.location.href = API + '/api/auth/google/login';
        } else {
          showAlert('Google sign-in is not configured yet. Please use the email form.', 'error');
          g.disabled = false;
        }
      }).catch(function () {
        showAlert('Could not reach the server. Please use the email form.', 'error');
        g.disabled = false;
      });
    });
  }

  // Capture a token handed back by the OAuth callback (#token=...) or surface ?oauth=error.
  function handleOAuthRedirect() {
    if (window.location.hash && window.location.hash.indexOf('token=') !== -1) {
      var t = window.location.hash.split('token=')[1];
      if (t) {
        setToken(decodeURIComponent(t));
        window.location.replace('dashboard-user.html');
        return true;
      }
    }
    var qs = new URLSearchParams(window.location.search);
    if (qs.get('oauth')) {
      showAlert('Google sign-in failed (' + qs.get('oauth') + '). Please try again or use the email form.', 'error');
    }
    return false;
  }

  // ---------- SIGNUP ----------
  function initSignup() {
    if (getToken()) { window.location.href = 'dashboard-user.html'; return; }
    bindPasswordToggles();
    bindGoogle();
    var pw = document.getElementById('password');
    var bar = document.getElementById('pw-bar');
    if (pw && bar) {
      pw.addEventListener('input', function () {
        var v = pw.value, score = 0;
        if (v.length >= 8) score++;
        if (/[A-Z]/.test(v)) score++;
        if (/[0-9]/.test(v)) score++;
        if (/[^A-Za-z0-9]/.test(v)) score++;
        bar.className = 'pw-score-' + score;
        bar.style.width = (score * 25) + '%';
      });
    }
    var form = document.getElementById('signup-form');
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      clearErrors(form);
      var f = {
        full_name: form.full_name.value.trim(),
        email: form.email.value.trim(),
        phone: form.phone.value.trim(),
        password: form.password.value,
        confirm: form.confirm_password.value,
        business_name: form.business_name.value.trim(),
        website_url: form.website_url.value.trim(),
        industry: form.industry.value
      };
      var ok = true;
      if (!f.full_name) { fieldError('full_name', 'Full name is required'); ok = false; }
      if (!validEmail(f.email)) { fieldError('email', 'Enter a valid email'); ok = false; }
      if (!f.phone) { fieldError('phone', 'Phone is required'); ok = false; }
      if (f.password.length < 8) { fieldError('password', 'Min 8 characters'); ok = false; }
      if (f.password !== f.confirm) { fieldError('confirm_password', 'Passwords do not match'); ok = false; }
      if (!f.business_name) { fieldError('business_name', 'Business name is required'); ok = false; }
      if (!form.agree.checked) { fieldError('agree', 'You must agree to continue'); ok = false; }
      if (!ok) return;

      var btn = document.getElementById('submit-btn');
      btn.disabled = true; var label = btn.textContent; btn.textContent = 'Creating…';
      api('/api/auth/signup', 'POST', {
        full_name: f.full_name, email: f.email, phone: f.phone, password: f.password,
        business_name: f.business_name, website_url: f.website_url, industry: f.industry
      }).then(function (res) {
        if (res.ok && res.data.token) {
          setToken(res.data.token);
          window.location.href = 'dashboard-user.html';
        } else {
          showAlert(res.data.error || 'Signup failed. Please try again.', 'error');
          btn.disabled = false; btn.textContent = label;
        }
      }).catch(function () {
        showAlert('Network error. Please try again.', 'error');
        btn.disabled = false; btn.textContent = label;
      });
    });
  }

  // ---------- LOGIN ----------
  function initLogin() {
    if (handleOAuthRedirect()) return;
    if (getToken()) { window.location.href = 'dashboard-user.html'; return; }
    bindPasswordToggles();
    bindGoogle();
    var forgot = document.getElementById('forgot-link');
    if (forgot) forgot.addEventListener('click', function (e) {
      e.preventDefault();
      var email = prompt('Enter your account email to reset your password:');
      if (!email) return;
      api('/api/auth/forgot-password', 'POST', { email: email }).then(function (res) {
        showAlert(res.data.message || 'If an account exists, a reset link has been sent.', 'success');
      });
    });
    var form = document.getElementById('login-form');
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      clearErrors(form);
      var email = form.email.value.trim();
      var password = form.password.value;
      var ok = true;
      if (!validEmail(email)) { fieldError('email', 'Enter a valid email'); ok = false; }
      if (!password) { fieldError('password', 'Password is required'); ok = false; }
      if (!ok) return;
      var btn = document.getElementById('submit-btn');
      btn.disabled = true; var label = btn.textContent; btn.textContent = 'Signing in…';
      api('/api/auth/login', 'POST', { email: email, password: password }).then(function (res) {
        if (res.ok && res.data.token) {
          setToken(res.data.token);
          window.location.href = 'dashboard-user.html';
        } else {
          showAlert(res.data.error || 'Login failed.', 'error');
          btn.disabled = false; btn.textContent = label;
        }
      }).catch(function () {
        showAlert('Network error. Please try again.', 'error');
        btn.disabled = false; btn.textContent = label;
      });
    });
  }

  // ---------- DASHBOARD ----------
  function initDashboard() {
    if (!getToken()) { window.location.href = 'login.html'; return; }
    var logout = document.getElementById('logout-btn');
    if (logout) logout.addEventListener('click', function () {
      api('/api/auth/logout', 'POST').finally(function () {
        clearToken();
        window.location.href = 'login.html';
      });
    });

    api('/api/auth/me').then(function (res) {
      if (!res.ok) { clearToken(); window.location.href = 'login.html'; return; }
      var u = res.data.user;
      var nameEl = document.getElementById('user-name');
      if (nameEl) nameEl.textContent = (u.full_name || '').split(' ')[0] || 'there';
      ['full_name', 'email', 'phone', 'business_name', 'website_url', 'industry'].forEach(function (k) {
        var el = document.getElementById(k);
        if (el) el.value = u[k] || '';
      });
    });

    // Audit requests are stored server-side; show a friendly placeholder when none yet
    var auditList = document.getElementById('audit-list');
    if (auditList) {
      auditList.innerHTML = '<p class="muted">You have no audit requests yet. Request your first free audit below.</p>';
    }

    var pform = document.getElementById('profile-form');
    if (pform) pform.addEventListener('submit', function (e) {
      e.preventDefault();
      api('/api/auth/update', 'PUT', {
        full_name: pform.full_name.value.trim(),
        phone: pform.phone.value.trim(),
        business_name: pform.business_name.value.trim(),
        website_url: pform.website_url.value.trim(),
        industry: pform.industry.value.trim()
      }).then(function (res) {
        if (window.RankToast) RankToast(res.data.message || 'Profile saved', res.ok ? 'success' : 'error');
        else showAlert(res.data.message || 'Saved', res.ok ? 'success' : 'error');
      });
    });
  }

  window.RankAuth = {
    initSignup: initSignup,
    initLogin: initLogin,
    initDashboard: initDashboard,
    getToken: getToken,
    clearToken: clearToken
  };
})(window);
