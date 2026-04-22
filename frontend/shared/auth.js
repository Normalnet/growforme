/**
 * Shared auth helpers for SmartTechBuddy dashboards.
 * Include this script BEFORE any dashboard-specific code.
 */
const API = 'http://localhost:5000/api/v1';

export function getToken() {
  return sessionStorage.getItem('auth_token');
}

export function getUser() {
  try { return JSON.parse(sessionStorage.getItem('auth_user') || 'null'); }
  catch { return null; }
}

export function logout() {
  sessionStorage.removeItem('auth_token');
  sessionStorage.removeItem('auth_user');
  window.location.href = '../login/index.html';
}

/** Redirect to login if no valid token, and enforce allowed roles. */
export function requireAuth(...roles) {
  const token = getToken();
  const user  = getUser();
  if (!token || !user) {
    window.location.href = '../login/index.html';
    return null;
  }
  if (roles.length && !roles.includes(user.role)) {
    document.body.innerHTML = `
      <div style="display:flex;align-items:center;justify-content:center;height:100vh;font-family:sans-serif;flex-direction:column;gap:12px">
        <div style="font-size:48px">🚫</div>
        <h2>Access Denied</h2>
        <p>Your role (<strong>${user.role}</strong>) cannot access this page.</p>
        <a href="../login/index.html" style="color:#2d6a2d;font-weight:600">← Return to Login</a>
      </div>`;
    return null;
  }
  return user;
}

/** Authenticated fetch wrapper — auto-attaches Bearer token. */
export async function apiFetch(path, options = {}) {
  const token = getToken();
  const res = await fetch(`${API}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
      ...(options.headers || {}),
    },
  });
  if (res.status === 401) { logout(); return null; }
  return res;
}

/** Render top nav bar into #navbar element. */
export function renderNav(user) {
  const ROLE_LABELS = {
    admin: 'System Admin', warehouse_mgr: 'Warehouse Manager',
    field_agent: 'Field Agent', supervisor: 'Supervisor', farmer: 'Farmer',
  };
  const nav = document.getElementById('navbar');
  if (!nav) return;
  nav.innerHTML = `
    <div class="nav-brand">🌱 SmartTechBuddy</div>
    <div class="nav-center">${document.title}</div>
    <div class="nav-right">
      <span class="nav-user">
        <span class="nav-role-badge">${ROLE_LABELS[user.role] || user.role}</span>
        ${user.name}
      </span>
      <button class="nav-logout" onclick="window.authLogout()">Sign Out</button>
    </div>`;
  window.authLogout = logout;
}
