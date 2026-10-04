import { useEffect, useState } from "react";

type WorkspaceFeedbackProps = {
  kind: "error" | "success";
  message: string;
  onDismiss: () => void;
};

export function WorkspaceFeedback({
  kind,
  message,
  onDismiss,
}: WorkspaceFeedbackProps) {
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    setDismissed(false);
  }, [message]);

  if (dismissed) return null;

  return (
    <div
      className={`workspace-feedback workspace-feedback-${kind}`}
      role={kind === "error" ? "alert" : "status"}
      aria-live={kind === "error" ? "assertive" : "polite"}
    >
      <span>{message}</span>
      <button
        type="button"
        className="workspace-feedback-dismiss"
        aria-label="Dismiss notification"
        onClick={() => {
          setDismissed(true);
          onDismiss();
        }}
      >
        ×
      </button>
    </div>
  );
}
