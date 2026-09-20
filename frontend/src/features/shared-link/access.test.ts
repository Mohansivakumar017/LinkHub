import { describe, expect, it } from "vitest";
import { describeSharedLinkFailure } from "./access";

describe("shared-link access", () => {
  it("requests a password for protected links", () => {
    expect(describeSharedLinkFailure(401, "link password required").kind).toBe("password");
  });

  it("preserves private-link authentication guidance", () => {
    expect(describeSharedLinkFailure(401, "private link requires authentication").kind).toBe("authentication");
  });
});
