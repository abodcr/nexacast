const API_BASE = "/api";

async function parseResponse(res) {
  const contentType = res.headers.get("content-type") || "";
  const isJson = contentType.includes("application/json");
  const data = isJson ? await res.json() : await res.text();

  if (!res.ok) {
    if (isJson && data?.detail) {
      throw new Error(data.detail);
    }
    throw new Error(typeof data === "string" ? data : `HTTP ${res.status}`);
  }

  return data;
}

export async function api(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  return parseResponse(res);
}
