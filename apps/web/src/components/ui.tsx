"use client";
import { useEffect, useId, useRef, useState } from "react";
import { ApiError, errorMessage } from "@/lib/api/client";
export function ErrorBox({
  error,
  retry,
}: {
  error: unknown;
  retry?: () => void;
}) {
  return (
    <div className="notice danger" role="alert">
      <strong>Something needs attention</strong>
      <p>{errorMessage(error)}</p>
      {error instanceof ApiError && error.requestId && (
        <p>
          Support ID: <code>{error.requestId}</code>
        </p>
      )}
      {retry && (
        <button className="button small" onClick={retry}>
          Try again
        </button>
      )}
    </div>
  );
}
export function Loading({
  label = "Loading your research…",
}: {
  label?: string;
}) {
  return (
    <div className="loading" role="status">
      <span className="spinner" />
      {label}
    </div>
  );
}
export function Empty({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="empty">
      <div className="empty-mark" aria-hidden="true">
        ↗
      </div>
      <h2>{title}</h2>
      <p>{children}</p>
    </div>
  );
}
export function Badge({
  children,
  tone = "neutral",
}: {
  children: React.ReactNode;
  tone?: string;
}) {
  return <span className={"badge " + tone}>{children}</span>;
}
export function Confirm({
  title,
  description,
  label,
  onConfirm,
}: {
  title: string;
  description: string;
  label?: string;
  onConfirm: () => Promise<void>;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const dialogTitle = useId();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  useEffect(() => {
    const node = dialog.current;
    return () => node?.close();
  }, []);
  async function confirm() {
    setBusy(true);
    setError(undefined);
    try {
      await onConfirm();
      dialog.current?.close();
    } catch (error) {
      setError(error);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <button
        className="button small danger-outline"
        onClick={() => {
          setError(undefined);
          dialog.current?.showModal();
        }}
      >
        {label || title}
      </button>
      <dialog
        ref={dialog}
        aria-labelledby={dialogTitle}
        onCancel={(event) => {
          if (busy) event.preventDefault();
        }}
      >
        <h2 id={dialogTitle}>{title}?</h2>
        <p>{description}</p>
        {!!error && <ErrorBox error={error} />}
        <div className="actions">
          <button
            className="button"
            disabled={busy}
            onClick={() => dialog.current?.close()}
          >
            Cancel
          </button>
          <button
            className="button danger-button"
            disabled={busy}
            onClick={() => void confirm()}
          >
            {busy ? "Working…" : "Confirm " + title.toLowerCase()}
          </button>
        </div>
      </dialog>
    </>
  );
}
export function PageHeading({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow?: string;
  title: string;
  description: string;
  action?: React.ReactNode;
}) {
  return (
    <header className="page-heading">
      <div>
        {eyebrow && <div className="eyebrow">{eyebrow}</div>}
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {action}
    </header>
  );
}
export function Pager({
  offset,
  count,
  size,
  onChange,
}: {
  offset: number;
  count: number;
  size: number;
  onChange: (value: number) => void;
}) {
  return (
    <nav className="pager" aria-label="Pagination">
      <button
        className="button small"
        disabled={!offset}
        onClick={() => onChange(Math.max(0, offset - size))}
      >
        Previous
      </button>
      <span>
        Page {Math.floor(offset / size) + 1} · {count} loaded
      </span>
      <button
        className="button small"
        disabled={count < size}
        onClick={() => onChange(offset + size)}
      >
        Next
      </button>
    </nav>
  );
}
export function date(value: string) {
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date(value));
}
export function validQuestion(value: string) {
  return (
    !!value.trim() &&
    [...value.trim()].length <= 2000 &&
    new TextEncoder().encode(value.trim()).length <= 6000 &&
    !/[\x00-\x08\x0b-\x1f]/.test(value)
  );
}
