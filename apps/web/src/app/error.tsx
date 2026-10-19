"use client";
export default function ErrorPage({ reset }: { reset: () => void }) {
  return (
    <main className="empty" role="alert">
      <h1>This page could not be loaded</h1>
      <p>Try again. Your saved research remains on the server.</p>
      <button className="button primary" onClick={reset}>
        Try again
      </button>
    </main>
  );
}
