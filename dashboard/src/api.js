const API_BASE = "/api";

async function apiFetch(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status}: ${text}`);
  }
  return res.json();
}

export function fetchReviews({ page = 1, pageSize = 20, userId, status, scoreMin, scoreMax } = {}) {
  const params = new URLSearchParams({ page, page_size: pageSize });
  if (userId) params.set("user_id", userId);
  if (status) params.set("status", status);
  if (scoreMin != null) params.set("score_min", scoreMin);
  if (scoreMax != null) params.set("score_max", scoreMax);
  return apiFetch(`/reviews?${params}`);
}

export function fetchReview(id) {
  return apiFetch(`/reviews/${id}`);
}

export function fetchReviewExplain(id) {
  return apiFetch(`/reviews/${id}/explain`);
}

export function overrideReview(id, payload) {
  return apiFetch(`/reviews/${id}/override`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function fetchDriftStatus() {
  return apiFetch("/drift/status");
}

export function runDriftCheck() {
  return apiFetch("/drift/run", {
    method: "POST",
  });
}

export function fetchStats() {
  return apiFetch("/stats");
}

export function fetchModelInfo() {
  return apiFetch("/model/info");
}

export function scoreBatch(items) {
  return apiFetch("/reviews/detect/batch", {
    method: "POST",
    body: JSON.stringify(items),
  });
}

export function fetchAuditLogs(limit = 100) {
  return apiFetch(`/reviews/audit/logs?limit=${limit}`);
}

export function fetchHealth() {
  return fetch("/health").then((r) => r.json());
}
