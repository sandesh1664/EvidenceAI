"use client";
import Link from "next/link";
import { useState } from "react";
import { useSession } from "@/lib/auth/session";
import { useResource } from "@/hooks/use-resource";
import { api, wsPath } from "@/lib/api/client";
import type { Workspace, Member } from "@/types/api";
import {
  Badge,
  Confirm,
  Empty,
  ErrorBox,
  Loading,
  PageHeading,
  Pager,
  date,
} from "@/components/ui";
import { useWorkspace } from "./context";
export function Workspaces() {
  const { user } = useSession();
  const [offset, setOffset] = useState(0);
  const resource = useResource<Workspace[]>(
    `/api/v1/workspaces/?limit=12&offset=${offset}`,
    user?.id || "",
  );
  const [error, setError] = useState<unknown>();
  const [busy, setBusy] = useState(false);
  async function create(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const form = event.currentTarget;
    const data = new FormData(form);
    setBusy(true);
    setError(undefined);
    try {
      await api.createWorkspace(
        String(data.get("name")).trim(),
        String(data.get("description")).trim(),
      );
      form.reset();
      setOffset(0);
      resource.refresh();
    } catch (error) {
      setError(error);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <PageHeading
        eyebrow="YOUR RESEARCH, ORGANIZED"
        title="Your workspaces"
        description="Give every project a home. Keep its documents, questions and sources together."
      />
      <section className="panel create-workspace">
        <div>
          <div className="eyebrow">MAKE ROOM FOR A NEW IDEA</div>
          <h2>Create a workspace</h2>
          <p>A private project space, shared only with the members you add.</p>
        </div>
        <form onSubmit={create}>
          <label>
            Workspace name
            <input
              name="name"
              placeholder="e.g. Climate research"
              maxLength={200}
              required
              pattern=".*\S.*"
            />
          </label>
          <label>
            Description <span className="hint">optional</span>
            <input
              name="description"
              maxLength={10000}
              placeholder="What are you investigating?"
            />
          </label>
          <button className="button primary" disabled={busy}>
            {busy ? "Creating…" : "+ Create workspace"}
          </button>
          {!!error && <ErrorBox error={error} />}
        </form>
      </section>
      <div className="section-heading">
        <h2>All workspaces</h2>
        <span className="hint">Only workspaces you can access</span>
      </div>
      {resource.loading && !resource.data ? (
        <Loading />
      ) : resource.error ? (
        <ErrorBox error={resource.error} retry={resource.refresh} />
      ) : !resource.data?.length ? (
        <Empty title="Your next project starts here">
          Create your first workspace to add documents and start asking
          questions.
        </Empty>
      ) : (
        <div className="workspace-grid">
          {resource.data.map((workspace, index) => (
            <Link
              className="workspace-card"
              href={"/workspaces/" + workspace.id}
              key={workspace.id}
              prefetch={false}
            >
              <div className={"workspace-symbol symbol-" + (index % 3)}>
                {workspace.name.slice(0, 1).toUpperCase()}
              </div>
              <Badge>
                {workspace.owner_id === user?.id ? "Owner" : "Shared workspace"}
              </Badge>
              <h3>{workspace.name}</h3>
              <p>
                {workspace.description || "A focused space for your research."}
              </p>
              <div className="card-footer">
                Created {date(workspace.created_at)}
                <span aria-hidden="true">↗</span>
              </div>
            </Link>
          ))}
        </div>
      )}
      <Pager
        offset={offset}
        count={resource.data?.length || 0}
        size={12}
        onChange={setOffset}
      />
    </>
  );
}
export function Members() {
  const { workspace, role, account } = useWorkspace();
  const [offset, setOffset] = useState(0);
  const resource = useResource<Member[]>(
    wsPath(workspace.id) + `/members?limit=20&offset=${offset}`,
    account,
  );
  const [error, setError] = useState<unknown>();
  const [busy, setBusy] = useState(false);
  const [success, setSuccess] = useState("");
  const manager = role === "owner" || role === "admin";
  async function add(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const form = event.currentTarget;
    const data = new FormData(form);
    setBusy(true);
    setError(undefined);
    setSuccess("");
    try {
      await api.addMember(
        workspace.id,
        String(data.get("user_id")).trim(),
        String(data.get("role")) as "admin" | "member",
      );
      form.reset();
      setSuccess("Member added.");
      resource.refresh();
    } catch (error) {
      setError(error);
    } finally {
      setBusy(false);
    }
  }
  async function change(member: Member, next: "admin" | "member") {
    setError(undefined);
    setBusy(true);
    try {
      await api.changeRole(workspace.id, member.user_id, next);
      resource.refresh();
    } catch (error) {
      setError(error);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <PageHeading
        eyebrow={workspace.name}
        title="Workspace members"
        description="Manage who can work with this project's evidence. Conversation histories stay private to their owners."
      />
      {!!error && <ErrorBox error={error} />}
      <div role="status">{success}</div>
      {manager && (
        <section className="panel">
          <h2>Add a registered user</h2>
          <p className="hint">
            Use the account ID from their profile. The API does not provide an
            email directory or invitations.
          </p>
          <form className="inline-form" onSubmit={add}>
            <label>
              Account ID
              <input
                name="user_id"
                required
                pattern="[0-9a-fA-F-]{36}"
                placeholder="User UUID"
              />
            </label>
            <label>
              Role
              <select name="role" defaultValue="member">
                <option value="member">Member</option>
                <option value="admin">Admin</option>
              </select>
            </label>
            <button className="button primary" disabled={busy}>
              Add member
            </button>
          </form>
        </section>
      )}
      {resource.loading ? (
        <Loading />
      ) : resource.error ? (
        <ErrorBox error={resource.error} retry={resource.refresh} />
      ) : (
        <div className="panel member-list">
          {resource.data?.map((member) => {
            const allowed =
              (role === "owner" && member.role !== "owner") ||
              (role === "admin" && member.role === "member");
            return (
              <div className="member-row" key={member.id}>
                <span className="avatar">
                  {member.role.slice(0, 1).toUpperCase()}
                </span>
                <div className="member-id">
                  <strong>
                    {member.user_id === account
                      ? "You"
                      : member.role === "owner"
                        ? "Workspace owner"
                        : "Registered user"}
                  </strong>
                  <code>{member.user_id}</code>
                </div>
                <Badge>{member.role}</Badge>
                <div className="actions">
                  {allowed && (
                    <>
                      <label className="sr-only" htmlFor={"role-" + member.id}>
                        Role for {member.user_id}
                      </label>
                      <select
                        id={"role-" + member.id}
                        value={member.role}
                        disabled={busy}
                        onChange={(event) =>
                          void change(
                            member,
                            event.target.value as "admin" | "member",
                          )
                        }
                      >
                        <option value="member">Member</option>
                        <option value="admin">Admin</option>
                      </select>
                      <Confirm
                        title="Remove member"
                        description="This user will lose workspace access. Their saved history is retained according to the conversation retention policy."
                        onConfirm={() =>
                          api.removeMember(workspace.id, member.user_id)
                        }
                      />
                    </>
                  )}
                  {role === "owner" && member.user_id !== account && (
                    <Confirm
                      title="Transfer ownership"
                      description={`Make account ${member.user_id} the owner? Your role will become admin. This changes who controls workspace membership and deletion.`}
                      onConfirm={async () => {
                        await api.transfer(workspace.id, member.user_id);
                        resource.refresh();
                      }}
                    />
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
      <Pager
        offset={offset}
        count={resource.data?.length || 0}
        size={20}
        onChange={setOffset}
      />
    </>
  );
}
