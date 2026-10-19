import Link from "next/link";
export default function NotFound() {
  return (
    <main className="empty">
      <h1>Page not found</h1>
      <p>
        This page is unavailable. Your accessible workspaces are a good place to
        start.
      </p>
      <Link className="button primary" href="/workspaces">
        Open workspaces
      </Link>
    </main>
  );
}
