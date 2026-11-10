const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function token(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("ps_token");
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, msg: string) {
    super(msg);
    this.status = status;
  }
}

export async function api(path: string, init: RequestInit = {}) {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((init.headers as Record<string, string>) || {}),
  };
  const t = token();
  if (t) headers["Authorization"] = `Bearer ${t}`;
  const res = await fetch(`${BASE}${path}`, { ...init, headers });
  if (res.status === 401 && typeof window !== "undefined") {
    localStorage.removeItem("ps_token");
    if (!window.location.pathname.startsWith("/login")) window.location.href = "/login";
  }
  let data: unknown = null;
  try {
    data = await res.json();
  } catch {
    data = null;
  }
  if (!res.ok) {
    const msg =
      (data as { detail?: string } | null)?.detail || `Request failed (${res.status})`;
    throw new ApiError(res.status, msg);
  }
  return data;
}
