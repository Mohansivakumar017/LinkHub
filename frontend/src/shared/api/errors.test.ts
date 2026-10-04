import { describe, expect, it } from "vitest";
import { readApiErrorMessage } from "./errors";

describe("API error messages", () => {
  it("explains rate limits and uses Retry-After when provided", async () => {
    const response = new Response(JSON.stringify({
      error: { code: "rate_limit_exceeded", message: "rate limit exceeded" },
    }), { status: 429, headers: { "Retry-After": "4" } });

    await expect(readApiErrorMessage(response, "Request failed")).resolves.toBe(
      "Too many requests. Please wait 4 seconds before trying again.",
    );
  });

  it("turns validation details into field-level guidance", async () => {
    const response = new Response(JSON.stringify({
      error: {
        code: "validation_error",
        details: [{ location: ["body", "email"], message: "invalid email address" }],
      },
    }), { status: 422 });

    await expect(readApiErrorMessage(response, "Request failed")).resolves.toBe(
      "email: invalid email address",
    );
  });

  it("identifies temporary failure of the rate-limit service", async () => {
    const response = new Response(JSON.stringify({
      error: { code: "rate_limit_backend_unavailable" },
    }), { status: 503, headers: { "Retry-After": "5" } });

    await expect(readApiErrorMessage(response, "Request failed")).resolves.toBe(
      "LinkHub cannot verify this request right now. Retry in 5 seconds.",
    );
  });
});
