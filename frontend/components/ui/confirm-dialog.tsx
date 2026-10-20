import { AlertTriangle, X } from "lucide-react";

export function ConfirmDialog({
  title,
  message,
  busy = false,
  onCancel,
  onConfirm,
}: {
  title: string;
  message: string;
  busy?: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onCancel(); }}>
      <section className="confirm-dialog" role="alertdialog" aria-modal="true" aria-labelledby="confirm-title" aria-describedby="confirm-message">
        <button className="icon-button confirm-close" onClick={onCancel} aria-label="Close confirmation"><X size={17} /></button>
        <span className="confirm-icon"><AlertTriangle size={19} /></span>
        <h2 id="confirm-title">{title}</h2>
        <p id="confirm-message">{message}</p>
        <div className="form-actions"><button className="button button-light" onClick={onCancel} disabled={busy}>Cancel</button><button className="button button-danger" onClick={onConfirm} disabled={busy}>{busy ? "Deleting…" : "Delete"}</button></div>
      </section>
    </div>
  );
}