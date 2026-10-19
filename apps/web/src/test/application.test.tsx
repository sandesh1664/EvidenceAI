import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import { SessionProvider, useSession } from "@/lib/auth/session";
import { api, ApiError, request } from "@/lib/api/client";
import VerifyEmail from "@/app/verify-email/page";
import { AuthForm } from "@/components/auth/auth-form";
import { PrivateShell } from "@/components/layout/shell";
import { WorkspaceScope } from "@/components/workspaces/context";
import { Workspaces, Members } from "@/components/workspaces/workspaces";
import {
  Library,
  fileError,
  extractionLabel,
  indexingLabel,
} from "@/components/documents/library";
import { Research } from "@/components/chat/research";
import { Search } from "@/components/chat/search";
import {
  Conversations,
  ConversationThread,
} from "@/components/chat/conversations";
import { AnswerView } from "@/components/citations/answer";
import { Settings } from "@/components/layout/settings";
import type { IndexStatus, Message } from "@/types/api";
const navigation = vi.hoisted(() => ({
  push: vi.fn(),
  replace: vi.fn(),
  params: { workspaceId: "w1", conversationId: "c1" },
  path: "/workspaces/w1",
}));
vi.mock("next/navigation", () => ({
  useRouter: () => navigation,
  useParams: () => navigation.params,
  usePathname: () => navigation.path,
}));
vi.mock("next/link", () => ({
  default: ({
    children,
    href,
    ...props
  }: {
    children: ReactNode;
    href: string;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));
const user = {
  id: "u1",
  email: "researcher@example.com",
  display_name: "Rae",
  is_active: true,
  created_at: "2026-01-01T00:00:00Z",
};
const workspace = {
  id: "w1",
  name: "Climate research",
  description: "A real project",
  owner_id: "u1",
  created_at: user.created_at,
  updated_at: user.created_at,
};
const doc = {
  id: "d1",
  workspace_id: "w1",
  uploaded_by: "u1",
  original_filename: "solar.txt",
  mime_type: "text/plain",
  file_size: 55,
  checksum_sha256: "a".repeat(64),
  processing_status: "completed",
  processing_error: null,
  processing_attempts: 1,
  last_processed_at: user.created_at,
  created_at: user.created_at,
  updated_at: user.created_at,
};
const index: IndexStatus = {
  document_id: "d1",
  embedding_model: "fake:fake-hash-v1@1",
  dimensions: 128,
  state: "done",
  generation: "g",
  attempts: 1,
  total_chunks: 1,
  indexed_chunks: 1,
  current_generation_chunks: 1,
  error: null,
  last_attempt_at: user.created_at,
};
const citation = {
  citation_id: "C1",
  document_id: "d1",
  chunk_id: "ch1",
  filename: "solar.txt",
  page_number: 2,
  section: "Energy",
  source_ref: "document:d1/page:2",
  supporting_excerpt: "Solar panels convert sunlight into electricity.",
  char_start: 0,
  char_end: 46,
  claim_ids: ["A1"],
};
const claim = {
  claim_id: "A1",
  text: citation.supporting_excerpt,
  citation_ids: ["C1"],
};
const answer = {
  answer: citation.supporting_excerpt + " [C1]",
  status: "answered",
  reason: "validated_extracts",
  claims: [claim],
  citations: [citation],
  retrieved_evidence_count: 1,
  model_identifier: "mock:mock-extractive-v1@1",
  usage: null,
  request_id: "request-1",
};
const conversation = {
  id: "c1",
  workspace_id: "w1",
  owner_id: "u1",
  title: "Solar research",
  created_at: user.created_at,
  updated_at: user.created_at,
  last_activity_at: user.created_at,
  archived_at: null,
};
const userMessage: Message = {
  id: "m1",
  conversation_id: "c1",
  role: "user",
  content: "Solar panels",
  sequence: 1,
  created_at: user.created_at,
  generation_status: "completed",
  answer_status: null,
  reason: null,
  model_identifier: null,
  usage: null,
  claims: [],
  citations: [],
  retrieved_evidence_count: 0,
  request_id: null,
  generation_http_status: null,
};
const assistant: Message = {
  ...userMessage,
  id: "m2",
  role: "assistant",
  sequence: 2,
  content: answer.answer,
  answer_status: "answered",
  model_identifier: answer.model_identifier,
  reason: answer.reason,
  claims: [claim],
  citations: [
    {
      ...citation,
      id: "saved1",
      original_document_id: "d1",
      original_chunk_id: "ch1",
      ordering: 0,
      validation_metadata: { method: "exact_quote_v1" },
    },
  ],
};
let fetcher: ReturnType<typeof vi.fn>;
let handler: (url: string, init: RequestInit) => Response | Promise<Response>;
function response(data: unknown, status = 200) {
  return new Response(status === 204 ? null : JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
function defaults(url: string, init: RequestInit) {
  const path = new URL(url).pathname;
  if (path.endsWith("/auth/me")) return response(user);
  if (path === "/api/v1/workspaces/")
    return response(init.method === "POST" ? workspace : [workspace]);
  if (path.endsWith("/documents/"))
    return response(
      init.method === "POST" ? { ...doc, processing_status: "pending" } : [doc],
      init.method === "POST" ? 202 : 200,
    );
  if (path.endsWith("/index")) return response(index);
  if (path.endsWith("/members"))
    return response([
      {
        id: "member1",
        workspace_id: "w1",
        user_id: "u1",
        role: "owner",
        joined_at: user.created_at,
      },
    ]);
  if (path.endsWith("/conversations/c1/messages"))
    return response({ items: [], next_after_sequence: null });
  if (path.endsWith("/conversations/c1")) return response(conversation);
  if (path.endsWith("/conversations"))
    return response(
      init.method === "POST"
        ? conversation
        : { items: [conversation], next_cursor: null },
      init.method === "POST" ? 201 : 200,
    );
  if (path.endsWith("/ask")) return response(answer);
  if (path.endsWith("/search"))
    return response([
      {
        chunk_id: "ch1",
        document_id: "d1",
        filename: "solar.txt",
        excerpt: citation.supporting_excerpt,
        page_number: 2,
        section: "Energy",
        source_ref: citation.source_ref,
        similarity: 0.873,
        embedding_model: "fake:fake-hash-v1@1",
      },
    ]);
  return response(workspace);
}
beforeEach(() => {
  navigation.push.mockClear();
  navigation.replace.mockClear();
  handler = defaults;
  fetcher = vi.fn((url: string, init: RequestInit = {}) =>
    Promise.resolve(handler(url, init)),
  );
  vi.stubGlobal("fetch", fetcher);
});
function mount(component: ReactNode, scope = true) {
  return render(
    <SessionProvider>
      <PrivateShell>
        {scope ? <WorkspaceScope>{component}</WorkspaceScope> : component}
      </PrivateShell>
    </SessionProvider>,
  );
}

describe("cookie and error contracts", () => {
  it("includes credentials, no-store and CSRF without an auth token", async () => {
    await api.login(user.email, "safe test password");
    const [, options] = fetcher.mock.calls[0];
    expect(options.credentials).toBe("include");
    expect(options.cache).toBe("no-store");
    expect(options.headers.get("X-CSRF-Protection")).toBe("1");
    expect(options.headers.has("Authorization")).toBe(false);
    expect(localStorage.length).toBe(0);
  });
  it("leaves multipart Content-Type to the browser", async () => {
    await api.upload(
      "w1",
      new File(["valid"], "source.txt", { type: "text/plain" }),
    );
    const [, options] = fetcher.mock.calls[0];
    expect(options.body).toBeInstanceOf(FormData);
    expect(options.headers.has("Content-Type")).toBe(false);
  });
  it.each([400, 401, 403, 404, 409, 413, 422, 429, 500, 503])(
    "classifies HTTP %i without echoing validation inputs",
    async (status) => {
      handler = () =>
        response({ detail: [{ input: { password: "PRIVATE" } }] }, status);
      await expect(request("/api/v1/test")).rejects.toBeInstanceOf(ApiError);
      try {
        await request("/api/v1/test");
      } catch (error) {
        expect((error as Error).message).not.toContain("PRIVATE");
      }
    },
  );
  it("does not add CSRF to reads and honors AbortSignal", async () => {
    const controller = new AbortController();
    await api.me(controller.signal);
    expect(fetcher.mock.calls[0][1].signal).toBe(controller.signal);
    expect(fetcher.mock.calls[0][1].headers.has("X-CSRF-Protection")).toBe(
      false,
    );
  });
});
describe("authentication", () => {
  it.each([false, true])(
    "submits a real auth form, register=%s",
    async (register) => {
      render(
        <SessionProvider>
          <AuthForm register={register} />
        </SessionProvider>,
      );
      const actor = userEvent.setup();
      if (register) await actor.type(screen.getByLabelText("Full name"), "Rae");
      await actor.type(screen.getByLabelText("Email address"), user.email);
      await actor.type(screen.getByLabelText("Password"), "long safe password");
      await actor.click(
        screen.getByRole("button", {
          name: register ? "Create account" : "Sign in",
        }),
      );
      if (register) {
        await screen.findByRole("status");
        expect(navigation.replace).not.toHaveBeenCalled();
        expect(fetcher.mock.calls.filter(([url]) => url.endsWith("/login"))).toHaveLength(0);
      } else {
        await waitFor(() => expect(navigation.replace).toHaveBeenCalledWith("/workspaces"));
      }
      const calls = fetcher.mock.calls.filter(([url]) =>
        url.endsWith(register ? "/register" : "/login"),
      );
      expect(calls).toHaveLength(1);
      if (!register) expect(screen.getByLabelText("Password")).toHaveAttribute("autocomplete", "current-password");
    },
  );
  it("shows safe credential errors", async () => {
    handler = (url, init) =>
      url.endsWith("/login")
        ? response({ detail: "Invalid email or password" }, 401)
        : defaults(url, init);
    render(
      <SessionProvider>
        <AuthForm />
      </SessionProvider>,
    );
    await userEvent.type(screen.getByLabelText("Email address"), user.email);
    await userEvent.type(screen.getByLabelText("Password"), "not valid");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Invalid email or password",
    );
  });
  it("protects private navigation when the session expires", async () => {
    handler = () => response({ detail: "Authentication required" }, 401);
    mount(<p>PRIVATE DATA</p>, false);
    await waitFor(() =>
      expect(navigation.replace).toHaveBeenCalledWith("/login"),
    );
    expect(screen.queryByText("PRIVATE DATA")).not.toBeInTheDocument();
  });
  it("clears visible private data on a 401 event", async () => {
    mount(<p>PRIVATE DATA</p>, false);
    await screen.findByText("PRIVATE DATA");
    handler = () => response({}, 401);
    await request("/api/v1/test").catch(() => {});
    await waitFor(() =>
      expect(screen.queryByText("PRIVATE DATA")).not.toBeInTheDocument(),
    );
  });
});
describe("workspaces and permissions", () => {
  it("creates and switches actual workspaces", async () => {
    mount(<Workspaces />, false);
    await screen.findByRole("heading", { name: "Your workspaces" });
    await userEvent.type(
      screen.getByLabelText("Workspace name"),
      "New project",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "+ Create workspace" }),
    );
    await waitFor(() =>
      expect(
        fetcher.mock.calls.some(
          ([url, init]) =>
            url.includes("/workspaces/") && init.method === "POST",
        ),
      ).toBe(true),
    );
    await userEvent.selectOptions(
      screen.getByLabelText("Switch workspace"),
      "w1",
    );
    expect(navigation.push).toHaveBeenCalledWith("/workspaces/w1");
  });
  it.each(["owner", "admin", "member"])(
    "shows %s management permissions",
    async (role) => {
      handler = (url, init) =>
        new URL(url).pathname.endsWith("/w1")
          ? response({
              ...workspace,
              owner_id: role === "owner" ? "u1" : "other",
            })
          : url.includes("/members")
            ? response([
                {
                  id: "r",
                  user_id: "u1",
                  workspace_id: "w1",
                  role,
                  joined_at: user.created_at,
                },
              ])
            : defaults(url, init);
      mount(<Members />);
      await screen.findByRole("heading", { name: "Workspace members" });
      await waitFor(() =>
        expect(
          screen.queryByText("Loading your research…"),
        ).not.toBeInTheDocument(),
      );
      if (role === "member")
        expect(
          screen.queryByRole("heading", { name: "Add a registered user" }),
        ).not.toBeInTheDocument();
      else
        expect(
          await screen.findByRole("heading", { name: "Add a registered user" }),
        ).toBeInTheDocument();
    },
  );
});
describe("documents", () => {
  it.each(["exe", "html", "markdown"])(
    "rejects unsupported .%s files",
    (extension) => {
      expect(fileError(new File(["test"], "document." + extension))).toContain(
        "PDF",
      );
    },
  );
  it("rejects empty and oversized files", () => {
    expect(fileError(new File([], "empty.txt"))).toContain("empty");
    const file = new File(["x"], "large.pdf");
    Object.defineProperty(file, "size", { value: 30 * 1024 * 1024 });
    expect(fileError(file)).toContain("limit");
  });
  it("maps real extraction/index states with no made-up percentages", () => {
    expect(extractionLabel({ processing_status: "completed" })).toBe(
      "Extraction complete",
    );
    expect(indexingLabel({ ...index, state: "queued" })).toBe(
      "Pending indexing",
    );
    expect(indexingLabel(index)).toBe("Indexed");
  });
  it("uploads via the real file control and displays worker states", async () => {
    mount(<Library />);
    const input = await screen.findByLabelText("Upload documents");
    await userEvent.upload(
      input,
      new File(["some text"], "source.txt", { type: "text/plain" }),
    );
    expect(await screen.findByText(/1 file uploaded/)).toBeInTheDocument();
    expect(await screen.findByText("Extraction complete")).toBeInTheDocument();
    expect(await screen.findByText("Indexed")).toBeInTheDocument();
  });
  it("reports an upload failure and preserves server errors", async () => {
    handler = (url, init) =>
      url.includes("/documents/") && init.method === "POST"
        ? response({ detail: "File exceeds upload byte limit" }, 413)
        : defaults(url, init);
    mount(<Library />);
    await userEvent.upload(
      await screen.findByLabelText("Upload documents"),
      new File(["text"], "source.txt", { type: "text/plain" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "File exceeds upload byte limit",
    );
  });
  it("pages documents using the supported limit/offset contract", async () => {
    handler = (url, init) =>
      new URL(url).pathname.endsWith("/documents/") && init.method === "GET"
        ? response(
            Array.from({ length: 20 }, (_, i) => ({ ...doc, id: "d" + i })),
          )
        : defaults(url, init);
    mount(<Library />);
    await screen.findByLabelText("Filter this page by filename");
    await userEvent.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() =>
      expect(
        fetcher.mock.calls.some(([url]) => url.includes("offset=20")),
      ).toBe(true),
    );
  });
});
describe("research, citations and search", () => {
  it("renders grounded claims and clickable sources safely", async () => {
    render(
      <AnswerView
        content={answer.answer}
        status="answered"
        reason={answer.reason}
        model={answer.model_identifier}
        claims={[claim]}
        citations={[
          { ...citation, supporting_excerpt: "<img src=x onerror=alert(1)>" },
        ]}
        workspace="w1"
      />,
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Open source C1" }),
    );
    expect(
      screen.getByRole("region", { name: "Source details" }),
    ).toHaveTextContent("<img src=x onerror=alert(1)>");
    expect(document.querySelector("img")).toBeNull();
    expect(
      screen.getByText("Offline mock · source selection"),
    ).toBeInTheDocument();
  });
  it("handles deleted historical sources", async () => {
    render(
      <AnswerView
        content={answer.answer}
        status="answered"
        reason={answer.reason}
        model={answer.model_identifier}
        claims={[claim]}
        citations={[{ ...citation, document_id: null, chunk_id: null }]}
        workspace="w1"
      />,
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Open source C1" }),
    );
    expect(screen.getByText("Original document deleted")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Download original" }),
    ).not.toBeInTheDocument();
  });
  it("asks the RAG endpoint and displays insufficient evidence", async () => {
    handler = (url, init) =>
      url.endsWith("/ask")
        ? response({
            ...answer,
            status: "insufficient_evidence",
            reason: "no_evidence",
            answer: "No adequate evidence.",
            claims: [],
            citations: [],
          })
        : defaults(url, init);
    mount(<Research />);
    await userEvent.type(
      await screen.findByLabelText("Your research question"),
      "Solar panels",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Ask question ↗" }),
    );
    expect(
      await screen.findByText("No adequate evidence."),
    ).toBeInTheDocument();
    expect(screen.getByText("insufficient evidence")).toBeInTheDocument();
  });
  it("renders provider-disabled envelopes instead of claiming live AI", async () => {
    handler = (url, init) =>
      url.endsWith("/ask")
        ? response(
            {
              ...answer,
              status: "provider_error",
              reason: "provider_disabled",
              answer: "Generation unavailable.",
              claims: [],
              citations: [],
            },
            503,
          )
        : defaults(url, init);
    mount(<Research />);
    await userEvent.type(
      await screen.findByLabelText("Your research question"),
      "Solar panels",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Ask question ↗" }),
    );
    expect(
      await screen.findByText(/configured provider is disabled/),
    ).toBeInTheDocument();
  });
  it("searches with document filters and displays ranked passages", async () => {
    mount(<Search />);
    await userEvent.type(
      await screen.findByLabelText("Search query"),
      "Solar panels",
    );
    await userEvent.click(
      screen.getByText("Sources · all workspace documents"),
    );
    await userEvent.click(screen.getByLabelText("Use all workspace documents"));
    await userEvent.click(await screen.findByLabelText(/solar.txt/));
    await userEvent.click(
      screen.getByRole("button", { name: "Search passages" }),
    );
    expect(await screen.findByText("Similarity 0.873")).toBeInTheDocument();
    const call = fetcher.mock.calls.find(([url]) => url.endsWith("/search"));
    expect(JSON.parse(call![1].body)).toMatchObject({
      query: "Solar panels",
      document_ids: ["d1"],
    });
  });
});
describe("persistent conversations", () => {
  it("creates and opens a conversation", async () => {
    mount(<Conversations />);
    await userEvent.type(
      await screen.findByLabelText("Conversation title"),
      "Solar research",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "+ New conversation" }),
    );
    await waitFor(() =>
      expect(navigation.push).toHaveBeenCalledWith(
        "/workspaces/w1/conversations/c1",
      ),
    );
  });
  it("renders ordered history and saved citations", async () => {
    handler = (url, init) =>
      url.includes("/messages")
        ? response({
            items: [userMessage, assistant],
            next_after_sequence: null,
          })
        : defaults(url, init);
    mount(<ConversationThread />);
    const messages = await screen.findByRole("region", {
      name: "Conversation messages",
    });
    expect(within(messages).getByText("You")).toBeInTheDocument();
    expect(messages.textContent!.indexOf("#1")).toBeLessThan(
      messages.textContent!.indexOf("#2"),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Open source C1" }),
    );
    expect(
      screen.getByRole("region", { name: "Source details" }),
    ).toHaveTextContent("Solar panels");
  });
  it("retries an uncertain follow-up with the identical idempotency key and payload", async () => {
    const bodies: string[] = [];
    handler = (url, init) => {
      if (url.includes("/messages") && init.method === "POST") {
        bodies.push(init.body as string);
        if (bodies.length === 1) throw new TypeError("Connection interrupted");
        return response({
          user_message: { ...userMessage, content: "What is their warranty?" },
          assistant_message: assistant,
          replayed: true,
        });
      }
      return defaults(url, init);
    };
    mount(<ConversationThread />);
    await userEvent.type(
      await screen.findByLabelText("Ask a follow-up question"),
      "What is their warranty?",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Send question ↗" }),
    );
    expect(
      await screen.findByText(/request may already have been saved/),
    ).toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("button", { name: "Retry same submission" }),
    );
    await waitFor(() => expect(bodies).toHaveLength(2));
    expect(bodies[0]).toEqual(bodies[1]);
    expect(JSON.parse(bodies[0]).idempotency_key).toMatch(/^[a-f0-9-]{36}$/);
  });
});
it("shows only supported profile settings and stores just a theme", async () => {
  mount(<Settings />, false);
  await screen.findByRole("heading", { name: "Your settings" });
  expect(screen.getByText("Configuration not exposed")).toBeInTheDocument();
  await userEvent.selectOptions(screen.getByLabelText("Theme"), "dark");
  expect(document.documentElement.dataset.theme).toBe("dark");
  expect(localStorage.getItem("evidenceai:theme")).toBe("dark");
  expect(screen.queryByLabelText(/API key/i)).not.toBeInTheDocument();
});

it("supports drag-and-drop upload with real multipart submission", async () => {
  mount(<Library />);
  await screen.findByLabelText("Upload documents");
  fireEvent.drop(
    screen.getByText("Bring your sources together").closest(".upload-zone")!,
    {
      dataTransfer: {
        files: [
          new File(["evidence"], "dropped.md", { type: "text/markdown" }),
        ],
      },
    },
  );
  expect(await screen.findByText(/1 file uploaded/)).toBeInTheDocument();
  const upload = fetcher.mock.calls.find(
    ([url, init]) =>
      new URL(url).pathname.endsWith("/documents/") && init.method === "POST",
  );
  expect((upload![1].body as FormData).get("file")).toHaveProperty(
    "name",
    "dropped.md",
  );
});

it("keeps archived conversation history read-only", async () => {
  handler = (url, init) =>
    new URL(url).pathname.endsWith("/conversations/c1")
      ? response({ ...conversation, archived_at: user.created_at })
      : defaults(url, init);
  mount(<ConversationThread />);
  expect(
    await screen.findByText(/Archived conversations accept no new questions/),
  ).toBeInTheDocument();
  expect(
    screen.queryByLabelText("Ask a follow-up question"),
  ).not.toBeInTheDocument();
});

it("pages saved conversations with the server cursor", async () => {
  handler = (url, init) =>
    new URL(url).pathname.endsWith("/conversations")
      ? response({ items: [conversation], next_cursor: "c1" })
      : defaults(url, init);
  mount(<Conversations />);
  await screen.findByRole("heading", { name: "Your research history" });
  await screen.findByText("Solar research");
  await userEvent.click(screen.getByRole("button", { name: "Next" }));
  await waitFor(() =>
    expect(fetcher.mock.calls.some(([url]) => url.includes("cursor=c1"))).toBe(
      true,
    ),
  );
});

it("ignores a late initial session response after a new login", async () => {
  function Identity() {
    const session = useSession();
    return (
      <span data-testid="session-identity">
        {session.user?.display_name || "Anonymous"}
      </span>
    );
  }
  let initial: (response: Response) => void = () => {};
  let seen = 0;
  handler = (url, init) => {
    if (url.endsWith("/auth/me")) {
      seen++;
      if (seen === 1)
        return new Promise((resolve) => {
          initial = resolve;
        });
      return response({ ...user, id: "new-user", display_name: "New account" });
    }
    return defaults(url, init);
  };
  render(
    <SessionProvider>
      <AuthForm />
      <Identity />
    </SessionProvider>,
  );
  await userEvent.type(screen.getByLabelText("Email address"), user.email);
  await userEvent.type(
    screen.getByLabelText("Password"),
    "a long safe password",
  );
  await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
  await waitFor(() =>
    expect(navigation.replace).toHaveBeenCalledWith("/workspaces"),
  );
  const initialCall = fetcher.mock.calls.find(([url]) =>
    url.endsWith("/auth/me"),
  );
  expect(initialCall![1].signal.aborted).toBe(true);
  initial(
    response({ ...user, id: "old-user", display_name: "Old private account" }),
  );
  await new Promise((resolve) => setTimeout(resolve, 0));
  expect(navigation.replace).toHaveBeenCalledTimes(1);
  expect(screen.getByTestId("session-identity")).toHaveTextContent(
    "New account",
  );
});


describe("email verification", () => {
  it("posts the fragment token and clears it without creating a session", async () => {
    window.history.replaceState(null, "", "/verify-email#token=" + "a".repeat(43));
    render(<VerifyEmail />);
    await userEvent.click(screen.getByRole("button", { name: "Verify email" }));
    await screen.findByRole("status");
    expect(window.location.hash).toBe("");
    const calls = fetcher.mock.calls.filter(([url]) => url.endsWith("/verify-registration"));
    expect(calls).toHaveLength(1);
    expect(JSON.parse(calls[0][1].body)).toEqual({ token: "a".repeat(43) });
    expect(fetcher.mock.calls.filter(([url]) => url.endsWith("/login"))).toHaveLength(0);
  });
  it("supports a manually pasted token when a link is unavailable", async () => {
    window.history.replaceState(null, "", "/verify-email");
    render(<VerifyEmail />);
    await userEvent.type(screen.getByLabelText("Verification token"), "b".repeat(43));
    await userEvent.click(screen.getByRole("button", { name: "Verify email" }));
    await screen.findByRole("status");
    expect(screen.getByRole("link", { name: "Sign in" })).toBeVisible();
  });
});
