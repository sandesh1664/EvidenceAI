import type {
  Answer,
  Conversation,
  Document,
  Member,
  Question,
  SearchResult,
  Turn,
  User,
  Workspace,
} from "@/types/api";

const configuredOrigin = (
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"
).replace(/\/$/, "");
export const API_ORIGIN =
  configuredOrigin === "same-origin" ? "" : configuredOrigin;
const origin = new URL(API_ORIGIN || "https://same-origin.invalid");
if (
  API_ORIGIN &&
  (origin.origin !== API_ORIGIN ||
    !["http:", "https:"].includes(origin.protocol) ||
    origin.username ||
    origin.password ||
    (origin.protocol === "http:" &&
      !["localhost", "127.0.0.1", "[::1]"].includes(origin.hostname)))
)
  throw new Error(
    "API URL must be an HTTPS origin (HTTP loopback is allowed for development).",
  );
const names: Record<number, string> = {
  400: "The request could not be understood.",
  401: "Your session has expired. Please sign in.",
  403: "This action is not permitted. Check your access and the trusted frontend origin.",
  404: "This resource is unavailable or you no longer have access.",
  409: "This action conflicts with the current state. Refresh and retry.",
  413: "This file exceeds the server upload limit.",
  422: "Please check the form values.",
  429: "Too many requests. Wait before retrying.",
};
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public payload?: unknown,
    public retryAfter?: string | null,
    public requestId?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}
function safeRequestId(response: Response): string | undefined {
  const value = response.headers.get("X-Request-ID");
  return value &&
    /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(
      value,
    )
    ? value
    : undefined;
}
export function invalidate() {
  if (typeof window !== "undefined")
    window.dispatchEvent(new Event("evidenceai:invalidate"));
}
export function errorMessage(error: unknown): string {
  return error instanceof ApiError
    ? error.message
    : "Cannot reach the API. Check your connection and try again.";
}
export async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  if (!path.startsWith("/api/v1/") || path.includes("://"))
    throw new Error("Invalid API path");
  const method = options.method || "GET";
  const headers = new Headers(options.headers);
  headers.set("X-Request-ID", crypto.randomUUID());
  if (method !== "GET" && method !== "HEAD")
    headers.set("X-CSRF-Protection", "1");
  if (options.body && !(options.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  const response = await fetch(API_ORIGIN + path, {
    ...options,
    method,
    headers,
    credentials: "include",
    cache: "no-store",
    redirect: "error",
  });
  const payload: unknown =
    response.status === 204
      ? undefined
      : await response.json().catch(() => undefined);
  options.signal?.throwIfAborted();
  if (!response.ok) {
    if (
      response.status === 401 &&
      !path.endsWith("/login") &&
      typeof window !== "undefined"
    )
      window.dispatchEvent(new Event("evidenceai:expired"));
    // FastAPI validation objects can include the submitted password: never stringify them.
    const detail =
      payload && typeof payload === "object" && "detail" in payload
        ? (payload as { detail: unknown }).detail
        : null;
    const message =
      typeof detail === "string" && response.status < 500
        ? detail
        : names[response.status] ||
          "The service could not complete this request. Please retry.";
    throw new ApiError(
      response.status,
      message,
      payload,
      response.headers.get("Retry-After"),
      safeRequestId(response),
    );
  }
  if (method !== "GET" && method !== "HEAD") invalidate();
  return payload as T;
}
export const wsPath = (id: string) =>
  `/api/v1/workspaces/${encodeURIComponent(id)}`;
const json = (method: string, body?: unknown): RequestInit => ({
  method,
  ...(body === undefined ? {} : { body: JSON.stringify(body) }),
});
export const api = {
  me: (signal?: AbortSignal) => request<User>("/api/v1/auth/me", { signal }),
  login: (email: string, password: string) =>
    request<User>("/api/v1/auth/login", json("POST", { email, password })),
  register: (email: string, password: string, display_name: string) =>
    request<{ detail: string }>(
      "/api/v1/auth/register",
      json("POST", { email, password, display_name }),
    ),
  verifyRegistration: (token: string) => request<{ detail: string }>("/api/v1/auth/verify-registration", json("POST", { token })),
  logout: () => request<void>("/api/v1/auth/logout", json("POST")),
  createWorkspace: (name: string, description: string) =>
    request<Workspace>(
      "/api/v1/workspaces/",
      json("POST", { name, description: description || null }),
    ),
  renameWorkspace: (id: string, name: string) =>
    request<Workspace>(wsPath(id), json("PATCH", { name })),
  deleteWorkspace: (id: string) => request<void>(wsPath(id), json("DELETE")),
  addMember: (id: string, user_id: string, role: "admin" | "member") =>
    request<Member>(wsPath(id) + "/members", json("POST", { user_id, role })),
  changeRole: (id: string, user_id: string, role: "admin" | "member") =>
    request<Member>(
      wsPath(id) + "/members/" + user_id,
      json("PATCH", { role }),
    ),
  removeMember: (id: string, user_id: string) =>
    request<void>(wsPath(id) + "/members/" + user_id, json("DELETE")),
  transfer: (id: string, new_owner_id: string) =>
    request<Workspace>(
      wsPath(id) + "/transfer-ownership",
      json("POST", { new_owner_id }),
    ),
  upload: (id: string, file: File) => {
    const data = new FormData();
    data.set("file", file);
    return request<Document>(wsPath(id) + "/documents/", {
      method: "POST",
      body: data,
    });
  },
  removeDocument: (id: string, document: string) =>
    request<void>(wsPath(id) + "/documents/" + document, json("DELETE")),
  retryDocument: (id: string, document: string) =>
    request<Document>(
      wsPath(id) + "/documents/" + document + "/retry",
      json("POST"),
    ),
  index: (id: string, document: string, force = false) =>
    request(
      wsPath(id) + "/documents/" + document + "/index",
      json("POST", { force }),
    ),
  retryIndex: (id: string, document: string) =>
    request(
      wsPath(id) + "/documents/" + document + "/index/retry",
      json("POST"),
    ),
  ask: (id: string, question: Question, signal?: AbortSignal) =>
    request<Answer>(wsPath(id) + "/ask", { ...json("POST", question), signal }),
  search: (
    id: string,
    query: string,
    document_ids: string[] | null,
    limit: number,
    signal?: AbortSignal,
  ) =>
    request<SearchResult[]>(wsPath(id) + "/search", {
      ...json("POST", { query, document_ids, limit }),
      signal,
    }),
  createConversation: (id: string, title: string) =>
    request<Conversation>(
      wsPath(id) + "/conversations",
      json("POST", { title }),
    ),
  updateConversation: (
    id: string,
    cid: string,
    body: { title?: string; archived?: boolean },
  ) =>
    request<Conversation>(
      wsPath(id) + "/conversations/" + cid,
      json("PATCH", body),
    ),
  deleteConversation: (id: string, cid: string) =>
    request<void>(wsPath(id) + "/conversations/" + cid, json("DELETE")),
  send: (
    id: string,
    cid: string,
    body: Question & { idempotency_key: string },
  ) =>
    request<Turn>(
      wsPath(id) + "/conversations/" + cid + "/messages",
      json("POST", body),
    ),
};
export async function downloadDocument(
  workspace: string,
  id: string,
  filename: string,
) {
  const response = await fetch(
    API_ORIGIN + wsPath(workspace) + "/documents/" + id + "/download",
    {
      credentials: "include",
      cache: "no-store",
      redirect: "error",
      headers: { "X-Request-ID": crypto.randomUUID() },
    },
  );
  if (!response.ok) {
    if (response.status === 401)
      window.dispatchEvent(new Event("evidenceai:expired"));
    throw new ApiError(
      response.status,
      names[response.status] || "Download unavailable.",
      undefined,
      undefined,
      safeRequestId(response),
    );
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export async function ownRole(
  workspace: Workspace,
  userId: string,
  signal?: AbortSignal,
) {
  if (workspace.owner_id === userId) return "owner" as const;
  for (let offset = 0; ; offset += 100) {
    const rows = await request<Member[]>(
      wsPath(workspace.id) + `/members?limit=100&offset=${offset}`,
      { signal },
    );
    const self = rows.find((row) => row.user_id === userId);
    if (self) return self.role;
    if (rows.length < 100) return null;
  }
}
