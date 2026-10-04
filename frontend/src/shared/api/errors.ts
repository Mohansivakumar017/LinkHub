type ApiErrorBody = {
  detail?: string;
  error?: {
    code?: string;
    message?: string;
    details?: Array<{
      location?: Array<string | number>;
      message?: string;
    }>;
  };
};

export async function readApiErrorMessage(
  response: Response,
  fallback: string,
): Promise<string> {
  let body: ApiErrorBody = {};
  try {
    body = await response.clone().json() as ApiErrorBody;
  } catch {
    body = {};
  }

  const code = body.error?.code;
  if (response.status === 429 || code === "rate_limit_exceeded") {
    const retryAfter = Number(response.headers.get("Retry-After"));
    const wait = Number.isFinite(retryAfter) && retryAfter > 0
      ? ` Please wait ${retryAfter} second${retryAfter === 1 ? "" : "s"} before trying again.`
      : " Please wait a moment before trying again.";
    return `Too many requests.${wait}`;
  }
  if (response.status === 503 && code === "rate_limit_backend_unavailable") {
    const retryAfter = Number(response.headers.get("Retry-After"));
    const wait = Number.isFinite(retryAfter) && retryAfter > 0
      ? ` Retry in ${retryAfter} seconds.`
      : " Please try again shortly.";
    return `LinkHub cannot verify this request right now.${wait}`;
  }
  if (code === "network_error") {
    return "Could not reach LinkHub. Check your connection and try again.";
  }
  if (body.error?.details?.length) {
    return body.error.details
      .slice(0, 3)
      .map((item) => {
        const field = item.location?.filter(part => part !== "body").join(".");
        return field ? `${field}: ${item.message ?? "invalid value"}` : item.message ?? "Invalid value";
      })
      .join("; ");
  }

  return body.error?.message ?? body.detail ?? fallback;
}
