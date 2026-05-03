const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

let accessToken = null;

export function setAccessToken(token) {
  accessToken = token;
}

export function clearAccessToken() {
  accessToken = null;
}

function authHeaders() {
  if (!accessToken) return {};
  return { Authorization: `Bearer ${accessToken}` };
}

async function parseError(response, fallbackMessage) {
  const detail = await response.json().catch(() => ({}));
  if (typeof detail?.detail === "string") return detail.detail;
  if (detail?.detail?.message) return `${detail.detail.message}`;
  if (detail?.message) return detail.message;
  return fallbackMessage;
}

async function request(path, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    ...authHeaders(),
    ...(options.headers || {})
  };
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
    credentials: "include"
  });
  if (response.status === 401 && options.retry !== false) {
    const refreshed = await refresh();
    if (refreshed) {
      return request(path, { ...options, retry: false });
    }
  }
  return response;
}

export async function login(email, password) {
  const response = await request("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
    retry: false
  });
  if (!response.ok) {
    throw new Error(await parseError(response, "Login failed"));
  }
  const data = await response.json();
  setAccessToken(data.access_token);
  return data;
}

export async function refresh() {
  const response = await fetch(`${API_BASE}/api/auth/refresh`, {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json"
    }
  });
  if (!response.ok) {
    clearAccessToken();
    return false;
  }
  const data = await response.json();
  setAccessToken(data.access_token);
  return true;
}

export async function logout() {
  await fetch(`${API_BASE}/api/auth/logout`, {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json"
    }
  });
  clearAccessToken();
}

export async function getMe() {
  const response = await request("/api/auth/me");
  if (!response.ok) {
    throw new Error("Not authenticated");
  }
  return response.json();
}

export async function getCases(caseType) {
  const query = caseType ? `?case_type=${caseType}` : "";
  const response = await request(`/api/cases${query}`);
  if (!response.ok) {
    throw new Error("Failed to load cases");
  }
  return response.json();
}

export async function getCase(caseId) {
  const response = await request(`/api/cases/${caseId}`);
  if (!response.ok) {
    throw new Error("Failed to load case");
  }
  return response.json();
}

export async function createCase(payload) {
  const response = await request("/api/cases", {
    method: "POST",
    body: JSON.stringify(payload)
  });
  if (!response.ok) {
    throw new Error(await parseError(response, "Failed to create case"));
  }
  return response.json();
}

export async function updateCase(caseId, payload) {
  const response = await request(`/api/cases/${caseId}`, {
    method: "PUT",
    body: JSON.stringify(payload)
  });
  if (!response.ok) {
    throw new Error(await parseError(response, "Failed to update case"));
  }
  return response.json();
}

export async function endorseCase(caseId) {
  const response = await request(`/api/cases/${caseId}/endorse`, {
    method: "POST"
  });
  if (!response.ok) {
    throw new Error(await parseError(response, "Failed to endorse case"));
  }
  return response.json();
}

export async function getSimilarCases(caseId) {
  const response = await request(`/api/cases/${caseId}/similar`);
  if (!response.ok) {
    throw new Error("Failed to load similar cases");
  }
  return response.json();
}

export async function matchExperts(payload) {
  const response = await request("/api/routing/experts", {
    method: "POST",
    body: JSON.stringify(payload)
  });
  if (!response.ok) {
    throw new Error(await parseError(response, "Failed to match experts"));
  }
  return response.json();
}

export async function searchCases(payload) {
  const response = await request("/api/search/cases", {
    method: "POST",
    body: JSON.stringify(payload)
  });
  if (!response.ok) {
    throw new Error(await parseError(response, "Failed to search cases"));
  }
  return response.json();
}

export async function getRoiMetrics() {
  const response = await request("/api/metrics/roi");
  if (!response.ok) {
    throw new Error("Failed to load ROI metrics");
  }
  return response.json();
}

export async function getAdminLogs() {
  const response = await request("/api/admin/logs");
  if (!response.ok) {
    throw new Error(await parseError(response, "Failed to load admin logs"));
  }
  return response.json();
}

export async function getSystemMetrics() {
  const response = await request("/api/metrics/system");
  if (!response.ok) {
    throw new Error(await parseError(response, "Failed to load system metrics"));
  }
  return response.json();
}

export async function exportCases() {
  const response = await request("/api/admin/exports/cases");
  if (!response.ok) {
    throw new Error(await parseError(response, "Failed to export cases"));
  }
  return response.json();
}
