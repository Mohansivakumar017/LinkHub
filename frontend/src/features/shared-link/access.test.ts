import { describe, expect, it } from "vitest";
import { describeSharedLinkFailure } from "./access";

describe("shared-link access", () => {
  it("requests a password for protected links", () => {
    expect(describeSharedLinkFailure(401, "link password required").kind).toBe("password");
  });

  it("explains when the supplied password is incorrect", () => {
    expect(describeSharedLinkFailure(401, "invalid link password").message).toBe(
      "That password is incorrect. Try again.",
    );
  });

  it("preserves private-link authentication guidance", () => {
    expect(describeSharedLinkFailure(401, "private link requires authentication").kind).toBe("authentication");
  });

  it("explains when a click-limited link is exhausted", () => {
    expect(describeSharedLinkFailure(410, "click limit reached").message).toContain(
      "maximum number of opens",
    );
  });

  it("explains rate limits and retry timing", () => {
    expect(describeSharedLinkFailure(429, "rate limit exceeded", "3").message).toBe(
      "Too many requests to open links. Try again in 3 seconds.",
    );
  });

  it("explains when a link has expired", () => {
    expect(describeSharedLinkFailure(410, "url expired").message).toContain("has expired");
  });

  it("explains when a one-time link was already used", () => {
    expect(describeSharedLinkFailure(410, "one-time link already used").message).toContain(
      "already been opened",
    );
  });

  it("explains when the current member cannot access a private link", () => {
    expect(describeSharedLinkFailure(401, "private link access denied").message).toContain(
      "not a member",
    );
  });
});
