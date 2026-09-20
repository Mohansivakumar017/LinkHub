import { describe, expect, it } from "vitest";
import { appRoutes } from "./routes";

describe("account route separation", () => {
  it("keeps profile identity and settings security as separate pages", () => {
    expect(appRoutes.profile).not.toBe(appRoutes.settings);
    expect(appRoutes.profile).toBe("/profile");
    expect(appRoutes.settings).toBe("/settings");
  });
});
