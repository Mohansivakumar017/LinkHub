export type SharedLinkAccessState =
  | { kind: "password"; message: string }
  | { kind: "authentication"; message: string }
  | { kind: "error"; message: string };

export function describeSharedLinkFailure(
  status: number,
  detail: string,
  retryAfter?: string | null,
): SharedLinkAccessState {
  if (status === 401 && detail === "link password required") {
    return { kind: "password", message: "This link is password protected. Enter the password to continue." };
  }
  if (status === 401 && detail === "invalid link password") {
    return { kind: "password", message: "That password is incorrect. Try again." };
  }
  if (status === 401 && detail === "private link requires authentication") {
    return { kind: "authentication", message: "Sign in to continue. This link is restricted to organization members." };
  }
  if (status === 410 && detail === "click limit reached") {
    return { kind: "error", message: "This link has reached its maximum number of opens and is no longer available." };
  }
  if (status === 410 && detail === "one-time link already used") {
    return { kind: "error", message: "This one-time link has already been opened and cannot be reused." };
  }
  if (status === 410 && detail === "url expired") {
    return { kind: "error", message: "This link has expired and can no longer be opened." };
  }
  if (status === 429) {
    const seconds = Number(retryAfter);
    const wait = Number.isFinite(seconds) && seconds > 0
      ? ` Try again in ${seconds} second${seconds === 1 ? "" : "s"}.`
      : " Please wait a moment and try again.";
    return { kind: "error", message: `Too many requests to open links.${wait}` };
  }
  if (status === 503) {
    return { kind: "error", message: "The link service is temporarily unavailable. Please try again shortly." };
  }
  if (status === 401 && detail === "private link access denied") {
    return { kind: "error", message: "You are signed in, but your account is not a member of the organization that owns this private link." };
  }
  if (status === 404 && detail === "url not found") {
    return { kind: "error", message: "This link is unavailable. It may have been deleted or the link code may be incorrect." };
  }
  return { kind: "error", message: detail || "Could not open link" };
}
