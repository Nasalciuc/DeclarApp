"use client";

import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { createUpload } from "@/actions/upload";

type State =
  | { phase: "idle" }
  | { phase: "uploading"; name: string }
  | { phase: "error"; message: string };

export default function UploadDropzone() {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [state, setState] = useState<State>({ phase: "idle" });
  const [dragging, setDragging] = useState(false);

  async function handleFile(file: File) {
    setState({ phase: "uploading", name: file.name });
    let ticket;
    try {
      ticket = await createUpload(file.name);
    } catch {
      setState({
        phase: "error",
        message: "Serverul nu a putut pregăti încărcarea. Încearcă din nou.",
      });
      return;
    }
    if ("error" in ticket) {
      setState({ phase: "error", message: ticket.error });
      return;
    }
    try {
      const put = await fetch(ticket.url, {
        method: "PUT",
        headers: { "Content-Type": ticket.contentType },
        body: file,
      });
      if (!put.ok) throw new Error(`upload ${put.status}`);
      router.push(`/declarations/${ticket.id}`);
    } catch {
      setState({
        phase: "error",
        message: "Încărcarea în stocare a eșuat. Încearcă din nou.",
      });
    }
  }

  const busy = state.phase === "uploading";

  return (
    <div>
      <div
        className={`dropzone${dragging ? " dragging" : ""}`}
        role="button"
        tabIndex={0}
        onClick={() => !busy && inputRef.current?.click()}
        onKeyDown={(e) => {
          if ((e.key === "Enter" || e.key === " ") && !busy) {
            inputRef.current?.click();
          }
        }}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          const file = e.dataTransfer.files?.[0];
          if (file && !busy) void handleFile(file);
        }}
      >
        {busy ? (
          <div className="processing" style={{ justifyContent: "center" }}>
            <span className="spinner" />
            <span>Se încarcă {state.name}…</span>
          </div>
        ) : (
          <>
            <p style={{ fontWeight: 600 }}>
              Trage fișierul aici sau apasă pentru a alege
            </p>
            <p className="muted">PDF, PNG sau JPG</p>
          </>
        )}
      </div>

      <input
        ref={inputRef}
        type="file"
        accept=".pdf,.png,.jpg,.jpeg"
        hidden
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) void handleFile(file);
        }}
      />

      {state.phase === "error" && (
        <p className="error-text">{state.message}</p>
      )}
    </div>
  );
}
