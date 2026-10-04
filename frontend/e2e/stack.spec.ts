import { test, expect } from "@playwright/test";

const mailpitBaseUrl = process.env.E2E_MAILPIT_URL ?? "http://localhost:8025";

test("frontend and proxied API are reachable", async ({ page, request }) => {
  await page.goto("/");
  await expect(page).toHaveTitle(/LinkHub/i);
  await expect(page.locator("body")).toContainText(/LinkHub/i);

  const health = await request.get("/api/v1/health");
  expect(health.ok()).toBeTruthy();
  expect(await health.json()).toMatchObject({ status: "ok" });
});

test("shared-link entry route renders the access screen", async ({ page }) => {
  await page.goto("/?link=acceptance-test");
  await expect(page.getByRole("heading", { name: "Open shared link" })).toBeVisible();
  await expect(page.getByText("acceptance-test")).toBeVisible();
});

test("authentication entry reports registration and recovery outcomes", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Welcome back" })).toBeVisible();
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.getByRole("heading", { name: "Create your workspace" })).toBeVisible();
  await expect(page.getByLabel("Full name")).toBeVisible();
  await page.getByLabel("Email address").fill(`browser-register-${Date.now()}@example.com`);
  await page.getByLabel("Full name").fill("Browser Registration");
  await page.locator('input[autocomplete="new-password"]').fill("StrongPass123!");
  await page.getByRole("button", { name: "Create workspace" }).click();
  await expect(page.getByRole("status")).toHaveText("Account created. Check your email to verify it, then sign in.");

  await page.getByRole("button", { name: "Forgot password?" }).click();
  await expect(page.getByRole("heading", { name: "Account recovery" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Send recovery email" })).toBeVisible();
});

test("authentication entry enforces required fields", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Sign in", exact: true }).last().click();
  await expect(page.locator("input:invalid")).toHaveCount(2);
});

test("authenticated user can verify, create an organization, and rotate an API key", async ({ page, request }) => {
  const email = `e2e-${Date.now()}@example.com`;
  const password = "StrongPass123!";
  const register = await request.post("/api/v1/auth/register", {
    data: { email, password, full_name: "Acceptance User" },
  });
  expect(register.status()).toBe(201);

  const verificationToken = await test.step("read verification token from Mailpit", async () => {
    const deadline = Date.now() + 10_000;
    while (Date.now() < deadline) {
      const response = await request.get(`${mailpitBaseUrl}/api/v1/messages?limit=20`);
      const body = await response.json() as { messages: Array<{ ID: string; To: Array<{ Address: string }> }> };
      const message = body.messages.find((item) => item.To.some((recipient) => recipient.Address === email));
      if (message) {
        const detail = await request.get(`${mailpitBaseUrl}/api/v1/message/${message.ID}`);
        const detailBody = await detail.json() as { Text?: string };
        const token = detailBody.Text?.match(
          /verify your email: ([A-Za-z0-9_.-]+\.[A-Za-z0-9_.-]+\.[A-Za-z0-9_.-]+)/
        )?.[1];
        if (token) return token;
      }
      await new Promise((resolve) => setTimeout(resolve, 250));
    }
    throw new Error(`Verification email was not delivered for ${email}`);
  });

  const verify = await request.post("/api/v1/auth/verify-email", { data: { token: verificationToken } });
  expect(verify.status()).toBe(204);
  const login = await request.post("/api/v1/auth/login", { data: { email, password } });
  expect(login.status()).toBe(200);
  const tokens = await login.json() as { access_token: string; refresh_token: string };
  const refreshed = await request.post("/api/v1/auth/refresh", {
    data: { refresh_token: tokens.refresh_token },
  });
  expect(refreshed.status()).toBe(200);
  const refreshedTokens = await refreshed.json() as { access_token: string; refresh_token: string };
  const headers = { Authorization: `Bearer ${refreshedTokens.access_token}` };

  const organization = await request.post("/api/v1/organizations", {
    headers,
    data: { name: `Acceptance Org ${Date.now()}` },
  });
  expect(organization.status()).toBe(201);
  const { id: organizationId } = await organization.json() as { id: string };

  const invitedEmail = `invite-${Date.now()}@example.com`;
  const invitation = await request.post(`/api/v1/organizations/${organizationId}/invites`, {
    headers,
    data: { email: invitedEmail, role: "member" },
  });
  expect(invitation.status()).toBe(200);
  const { invite_id: inviteId, invite_token: originalInviteToken } = await invitation.json() as { invite_id: string; invite_token: string };
  const pendingInvites = await request.get(`/api/v1/organizations/${organizationId}/invites`, { headers });
  expect(pendingInvites.status()).toBe(200);
  expect(await pendingInvites.json()).toEqual(expect.arrayContaining([
    expect.objectContaining({ id: inviteId, invited_email: invitedEmail, role: "member", is_expired: false }),
  ]));
  const outstandingAdminInvite = await request.post(
    `/api/v1/organizations/${organizationId}/invites`,
    { headers, data: { email: invitedEmail, role: "admin" } },
  );
  expect(outstandingAdminInvite.status()).toBe(200);
  const { invite_token: outstandingAdminToken } = await outstandingAdminInvite.json() as { invite_token: string };
  const resend = await request.post(`/api/v1/organizations/${organizationId}/invites/${inviteId}/resend`, { headers });
  expect(resend.status()).toBe(200);
  const { invite_token: inviteToken } = await resend.json() as { invite_token: string };
  expect(inviteToken).not.toBe(originalInviteToken);

  const invitedRegistration = await request.post("/api/v1/auth/register", {
    data: { email: invitedEmail, password, full_name: "Invited User" },
  });
  expect(invitedRegistration.status()).toBe(201);
  const invitedVerificationToken = await test.step("read invited user verification token", async () => {
    const deadline = Date.now() + 10_000;
    while (Date.now() < deadline) {
      const response = await request.get(`${mailpitBaseUrl}/api/v1/messages?limit=30`);
      const body = await response.json() as { messages: Array<{ ID: string; To: Array<{ Address: string }> }> };
      const message = body.messages.find((item) => item.To.some((recipient) => recipient.Address === invitedEmail));
      if (message) {
        const detail = await request.get(`${mailpitBaseUrl}/api/v1/message/${message.ID}`);
        const detailBody = await detail.json() as { Text?: string };
        const token = detailBody.Text?.match(
          /verify your email: ([A-Za-z0-9_.-]+\.[A-Za-z0-9_.-]+\.[A-Za-z0-9_.-]+)/
        )?.[1];
        if (token) return token;
      }
      await new Promise((resolve) => setTimeout(resolve, 250));
    }
    throw new Error(`Verification email was not delivered for ${invitedEmail}`);
  });
  const invitedVerification = await request.post("/api/v1/auth/verify-email", {
    data: { token: invitedVerificationToken },
  });
  expect(invitedVerification.status()).toBe(204);
  const invitedLogin = await request.post("/api/v1/auth/login", {
    data: { email: invitedEmail, password },
  });
  expect(invitedLogin.status()).toBe(200);
  const invitedTokens = await invitedLogin.json() as { access_token: string };
  const invitedHeaders = { Authorization: `Bearer ${invitedTokens.access_token}` };
  const rejectedOldInvite = await request.post("/api/v1/organizations/invites/accept", {
    headers: invitedHeaders,
    data: { invite_token: originalInviteToken },
  });
  expect(rejectedOldInvite.status()).toBe(400);
  const accepted = await request.post("/api/v1/organizations/invites/accept", {
    headers: invitedHeaders,
    data: { invite_token: inviteToken },
  });
  expect(accepted.status()).toBe(200);
  const members = await request.get(`/api/v1/organizations/${organizationId}/members`, { headers });
  expect(members.status()).toBe(200);
  expect(await members.json()).toEqual(expect.arrayContaining([
    expect.objectContaining({ email: invitedEmail, role: "member" }),
  ]));
  const revokedEmail = `revoked-${Date.now()}@example.com`;
  const anotherInvite = await request.post(`/api/v1/organizations/${organizationId}/invites`, {
    headers,
    data: { email: revokedEmail, role: "member" },
  });
  expect(anotherInvite.status()).toBe(200);
  const { invite_id: revokedInviteId } = await anotherInvite.json() as { invite_id: string };
  const revokeInvite = await request.delete(
    `/api/v1/organizations/${organizationId}/invites/${revokedInviteId}`,
    { headers },
  );
  expect(revokeInvite.status()).toBe(204);
  const revokedInvites = await request.get(`/api/v1/organizations/${organizationId}/invites`, { headers });
  expect(await revokedInvites.json()).not.toEqual(expect.arrayContaining([
    expect.objectContaining({ id: revokedInviteId }),
  ]));

  const protectedLink = await request.post("/api/v1/urls", {
    headers,
    data: {
      organization_id: organizationId,
      original_url: "https://example.com/acceptance-protected",
      title: "Acceptance protected link",
      password: "LinkPass123!",
    },
  });
  expect(protectedLink.status()).toBe(201);
  const link = await protectedLink.json() as { short_code: string };
  const missingPassword = await request.get(`/api/v1/urls/resolve/${link.short_code}`);
  expect(missingPassword.status()).toBe(401);
  expect(await missingPassword.json()).toMatchObject({ error: { message: "link password required" } });
  const wrongPassword = await request.get(
    `/api/v1/urls/resolve/${link.short_code}?password=WrongPass123!`
  );
  expect(wrongPassword.status()).toBe(401);
  expect(await wrongPassword.json()).toMatchObject({ error: { message: "invalid link password" } });
  const correctPassword = await request.get(
    `/api/v1/urls/resolve/${link.short_code}?password=LinkPass123!`
  );
  expect(correctPassword.status()).toBe(200);
  expect(await correctPassword.json()).toMatchObject({
    original_url: "https://example.com/acceptance-protected",
  });

  await page.goto("/auth");
  await page.evaluate(({ accessToken, refreshToken, selectedOrganization }) => {
    localStorage.setItem("linkhub_access_token", accessToken);
    localStorage.setItem("linkhub_refresh_token", refreshToken);
    localStorage.setItem("linkhub_organization_id", selectedOrganization);
  }, {
    accessToken: tokens.access_token,
    refreshToken: tokens.refresh_token,
    selectedOrganization: organizationId,
  });
  await page.goto("/workspace/links");
  await page.locator(".organization-picker select").selectOption(organizationId);
  await page.getByRole("button", { name: "Load links" }).click();
  await page.getByRole("navigation", { name: "Link management" }).getByRole("link", { name: "Import CSV" }).click();
  await page.getByLabel("CSV content")
    .fill("original_url,title\nhttps://example.com/acceptance-import,Imported link");
  await page.getByRole("button", { name: "Import pasted links" }).click();
  await expect(page.getByRole("status")).toContainText("Imported 1 links.");

  const reusedAliasCode = `reuse-${Date.now()}`;
  const oldAlias = await request.post("/api/v1/urls", {
    headers,
    data: {
      organization_id: organizationId,
      original_url: "https://example.com/old-alias",
      custom_alias: reusedAliasCode,
      title: "Old alias",
      one_time: true,
    },
  });
  expect(oldAlias.status()).toBe(201);
  const firstOldAliasOpen = await page.evaluate(async (shortCode) => {
    const response = await fetch(`/api/v1/urls/resolve/${shortCode}`);
    return response.status;
  }, reusedAliasCode);
  expect(firstOldAliasOpen).toBe(200);
  const secondOldAliasOpen = await page.evaluate(async (shortCode) => {
    const response = await fetch(`/api/v1/urls/resolve/${shortCode}`);
    return response.status;
  }, reusedAliasCode);
  expect(secondOldAliasOpen).toBe(410);
  await page.getByLabel("CSV content")
    .fill(`original_url,custom_alias\nhttps://example.com/conflict,${reusedAliasCode}`);
  await page.getByRole("button", { name: "Import pasted links" }).click();
  await expect(page.getByRole("alert")).toContainText("already in use by an active link");
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await expect.poll(async () => {
    const bounds = await page.getByRole("alert").boundingBox();
    return bounds?.y;
  }).toBeGreaterThanOrEqual(0);
  expect((await page.getByRole("alert").boundingBox())?.y).toBeLessThan(80);
  await page.getByRole("button", { name: "Dismiss notification" }).click();
  await expect(page.getByRole("alert")).toHaveCount(0);

  await page.getByRole("navigation", { name: "Link management" }).getByRole("link", { name: "Manage links" }).click();
  await page.getByRole("button", { name: "Load links" }).click();
  const oldAliasRow = page.locator(".link-row").filter({ hasText: "Old alias" });
  await expect(oldAliasRow).toBeVisible();
  await oldAliasRow.getByRole("button", { name: "Delete" }).click();
  await expect(page.getByRole("dialog")).toContainText("existing bookmarks and QR codes");
  await page.getByRole("dialog").getByRole("button", { name: "Delete link" }).click();
  await expect(oldAliasRow).toHaveCount(0);

  await page.getByRole("navigation", { name: "Link management" }).getByRole("link", { name: "Import CSV" }).click();
  await page.getByLabel("CSV content")
    .fill(`original_url,custom_alias,one_time\nhttps://example.com/new-link,${reusedAliasCode},true`);
  await page.getByRole("button", { name: "Import pasted links" }).click();
  await expect(page.getByRole("status")).toContainText("Imported 1 links.");
  const sharedPage = await page.context().newPage();
  await sharedPage.route("https://example.com/new-link", (route) =>
    route.fulfill({ status: 200, body: "Replacement destination" }),
  );
  await sharedPage.goto(`/?link=${reusedAliasCode}`);
  await expect(sharedPage).toHaveURL("https://example.com/new-link");
  await sharedPage.close();
  const aliasHistory = await request.get(
    `/api/v1/analytics/organizations/${organizationId}/top-links?days=30&limit=100`,
    { headers },
  );
  expect(aliasHistory.status()).toBe(200);
  const aliasHistoryRows = (await aliasHistory.json() as Array<{
    short_code: string;
    is_deleted: boolean;
    clicks: number;
  }>).filter((row) => row.short_code === reusedAliasCode);
  expect(aliasHistoryRows).toHaveLength(2);
  expect(aliasHistoryRows).toEqual(expect.arrayContaining([
    expect.objectContaining({ is_deleted: true, clicks: 1 }),
    expect.objectContaining({ is_deleted: false, clicks: 1 }),
  ]));
  await page.getByRole("link", { name: /Analytics/ }).click();
  await expect(page.getByText("Deleted link history")).toBeVisible();
  await expect(
    page.locator(".analytics-grid article").nth(1).locator(".admin-row")
      .filter({ hasText: reusedAliasCode }),
  ).toHaveCount(2);
  await page.getByRole("link", { name: /Links/ }).click();
  await page.getByRole("navigation", { name: "Link management" }).getByRole("link", { name: "Manage links" }).click();
  await page.getByRole("button", { name: "Load links" }).click();
  const protectedLinkRow = page.locator(".link-row").filter({ hasText: "Acceptance protected link" });
  await expect(protectedLinkRow).toBeVisible();
  await protectedLinkRow.getByRole("button", { name: "Open" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.getByRole("dialog").getByLabel("Link password").fill("WrongPass123!");
  await page.getByRole("dialog").getByRole("button", { name: "Open link" }).click();
  await expect(page.getByRole("dialog").getByRole("alert")).toHaveText("That password is incorrect. Try again.");
  await page.getByRole("dialog").getByLabel("Link password").fill("LinkPass123!");
  await page.context().route("https://example.com/acceptance-protected", (route) =>
    route.fulfill({ status: 200, body: "Protected destination" }),
  );
  const destinationPagePromise = page.waitForEvent("popup");
  await page.getByRole("dialog").getByRole("button", { name: "Open link" }).click();
  const destinationPage = await destinationPagePromise;
  await expect(destinationPage).toHaveURL("https://example.com/acceptance-protected");
  await expect(page.getByRole("heading", { name: "Link workspace", level: 1 })).toBeVisible();
  await destinationPage.close();

  const limitedLinkResponse = await request.post("/api/v1/urls", {
    headers,
    data: {
      organization_id: organizationId,
      original_url: "https://example.com/acceptance-click-limited",
      title: "Acceptance click-limited link",
      click_limit: 1,
    },
  });
  expect(limitedLinkResponse.status()).toBe(201);
  await page.getByRole("button", { name: "Load links" }).click();
  const limitedLinkRow = page.locator(".link-row").filter({ hasText: "Acceptance click-limited link" });
  await expect(limitedLinkRow).toBeVisible();
  await page.context().route("https://example.com/acceptance-click-limited", (route) =>
    route.fulfill({ status: 200, body: "Click-limited destination" }),
  );
  const allowedOpen = page.waitForEvent("popup");
  const firstResolve = page.waitForResponse(response => response.url().includes("/urls/resolve/"));
  await limitedLinkRow.getByRole("button", { name: "Open" }).click();
  expect((await firstResolve).status()).toBe(200);
  const firstVisit = await allowedOpen;
  await expect(firstVisit).toHaveURL("https://example.com/acceptance-click-limited");
  await firstVisit.close();
  const limitedResolve = page.waitForResponse(response => response.url().includes("/urls/resolve/"));
  await limitedLinkRow.getByRole("button", { name: "Open" }).click();
  expect((await limitedResolve).status()).toBe(410);
  await expect(page.getByRole("alert")).toContainText("maximum number of opens");

  const concurrentLink = await request.post("/api/v1/urls", {
    headers,
    data: {
      organization_id: organizationId,
      original_url: "https://example.com/acceptance-concurrent-one-time",
      title: "Acceptance concurrent one-time link",
      one_time: true,
    },
  });
  expect(concurrentLink.status()).toBe(201);
  const { short_code: concurrentCode } = await concurrentLink.json() as { short_code: string };
  const concurrentOpens = await Promise.all(
    Array.from({ length: 8 }, () =>
      request.get(`/api/v1/urls/resolve/${concurrentCode}`),
    ),
  );
  expect(concurrentOpens.filter(response => response.status() === 200)).toHaveLength(1);
  expect(concurrentOpens.filter(response => response.status() === 410)).toHaveLength(7);

  const createdKey = await request.post("/api/v1/api-keys", {
    headers,
    data: { name: "Browser acceptance key" },
  });
  expect(createdKey.status()).toBe(201);
  const key = await createdKey.json() as { id: string; key: string };
  expect(key.key).toMatch(/^lhk_/);
  const apiKeyLinks = await request.get(`/api/v1/urls/api/organizations/${organizationId}`, {
    headers: { "X-API-Key": key.key },
  });
  expect(apiKeyLinks.status()).toBe(200);

  const rotatedKey = await request.post(`/api/v1/api-keys/${key.id}/rotate`, { headers });
  expect(rotatedKey.status()).toBe(201);
  const replacement = await rotatedKey.json() as { key: string };
  expect(replacement.key).toMatch(/^lhk_/);
  expect(replacement.key).not.toBe(key.key);

  const revoked = await request.delete(`/api/v1/api-keys/${key.id}`, { headers });
  expect(revoked.status()).toBe(204);
  const invitedProfile = await request.get("/api/v1/users/me", { headers: invitedHeaders });
  expect(invitedProfile.status()).toBe(200);
  const { id: invitedUserId } = await invitedProfile.json() as { id: string };
  const removed = await request.delete(
    `/api/v1/organizations/${organizationId}/members/${invitedUserId}`,
    { headers }
  );
  expect(removed.status()).toBe(204);
  const rejectedOutstandingInvite = await request.post(
    "/api/v1/organizations/invites/accept",
    { headers: invitedHeaders, data: { invite_token: outstandingAdminToken } },
  );
  expect(rejectedOutstandingInvite.status()).toBe(400);
  const logout = await request.post("/api/v1/auth/logout", {
    data: { refresh_token: refreshedTokens.refresh_token },
  });
  expect(logout.status()).toBe(204);
  const revokedRefresh = await request.post("/api/v1/auth/refresh", {
    data: { refresh_token: refreshedTokens.refresh_token },
  });
  expect(revokedRefresh.status()).toBe(401);

  await page.goto("/auth");
  await page.evaluate(({ accessToken, refreshToken }) => {
    localStorage.removeItem("linkhub_organization_id");
    localStorage.setItem("linkhub_access_token", accessToken);
    localStorage.setItem("linkhub_refresh_token", refreshToken);
  }, { accessToken: refreshedTokens.access_token, refreshToken: refreshedTokens.refresh_token });
  await page.goto("/organizations");
  await expect(page.getByRole("heading", { name: "Organizations & members", level: 1 })).toBeVisible();
  await expect(page.locator(".workspace-header-context")).toHaveText("All organizations");
  await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();
  await expect(page.locator(`option[value="${organizationId}"]`).first()).toBeAttached({ timeout: 5000 });
});
