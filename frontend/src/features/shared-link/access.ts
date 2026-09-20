export type SharedLinkAccessState =
  | { kind: "password"; message: string }
  | { kind: "authentication"; message: string }
  | { kind: "error"; message: string };

export function describeSharedLinkFailure(status: number, detail: string): SharedLinkAccessState {
  if (status === 401 && detail === "link password required") {
    return { kind: "password", message: "This link is password protected. Enter the password to continue." };
  }
  if (status === 401 && detail === "private link requires authentication") {
    return { kind: "authentication", message: "Sign in to continue. This link is restricted to organization members." };
  }
  return { kind: "error", message: detail || "Could not open link" };
}
