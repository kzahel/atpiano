import type { APIRoute } from "astro";
import { env } from "cloudflare:workers";

const CONSENT_VERSION = "hosted-interest-2026-08-25";
const SITEVERIFY_URL =
  "https://challenges.cloudflare.com/turnstile/v0/siteverify";

interface TurnstileResult {
  success: boolean;
  hostname?: string;
  action?: string;
  "error-codes"?: string[];
}

function isEmail(value: string): boolean {
  return value.length <= 254 && /^[^\s@]+@[^\s@]+\.[^\s@]+$/u.test(value);
}

function responseFor(
  request: Request,
  body: { ok: boolean; message: string },
  status: number,
): Response {
  if (request.headers.get("accept")?.includes("application/json")) {
    return Response.json(body, {
      status,
      headers: { "Cache-Control": "no-store" },
    });
  }

  if (body.ok) {
    return new Response(null, {
      status: 303,
      headers: {
        Location: "/?joined=1#hosted",
        "Cache-Control": "no-store",
      },
    });
  }

  return new Response(body.message, {
    status,
    headers: {
      "Cache-Control": "no-store",
      "Content-Type": "text/plain; charset=utf-8",
    },
  });
}

export const POST: APIRoute = async ({ request }) => {
  const requestUrl = new URL(request.url);
  const origin = request.headers.get("origin");
  if (origin && origin !== requestUrl.origin) {
    return responseFor(request, { ok: false, message: "Invalid request." }, 403);
  }

  let form: FormData;
  try {
    form = await request.formData();
  } catch {
    return responseFor(
      request,
      { ok: false, message: "Please submit the signup form again." },
      400,
    );
  }

  const honeypot = String(form.get("company") ?? "").trim();
  if (honeypot) {
    return responseFor(
      request,
      { ok: true, message: "Your interest has been recorded." },
      200,
    );
  }

  const email = String(form.get("email") ?? "").trim().toLowerCase();
  if (!isEmail(email)) {
    return responseFor(
      request,
      { ok: false, message: "Enter a valid email address." },
      400,
    );
  }

  const token = String(form.get("cf-turnstile-response") ?? "");
  if (!token) {
    return responseFor(
      request,
      { ok: false, message: "Complete the anti-spam check and try again." },
      400,
    );
  }

  if (!env.TURNSTILE_SECRET_KEY) {
    console.error("TURNSTILE_SECRET_KEY is not configured");
    return responseFor(
      request,
      { ok: false, message: "Signup is temporarily unavailable." },
      503,
    );
  }

  const validationBody = new FormData();
  validationBody.set("secret", env.TURNSTILE_SECRET_KEY);
  validationBody.set("response", token);
  validationBody.set("idempotency_key", crypto.randomUUID());

  let turnstile: TurnstileResult;
  try {
    const validationResponse = await fetch(SITEVERIFY_URL, {
      method: "POST",
      body: validationBody,
    });
    turnstile = await validationResponse.json<TurnstileResult>();
  } catch (error) {
    console.error("Turnstile validation failed", error);
    return responseFor(
      request,
      { ok: false, message: "The anti-spam check failed. Please try again." },
      502,
    );
  }

  const isLocalTest = requestUrl.hostname === "localhost";
  if (
    !turnstile.success ||
    (!isLocalTest && turnstile.action !== "hosted-interest")
  ) {
    console.warn("Turnstile rejected hosted-interest submission", {
      errorCodes: turnstile["error-codes"] ?? [],
      hostname: turnstile.hostname,
      action: turnstile.action,
    });
    return responseFor(
      request,
      { ok: false, message: "The anti-spam check expired. Please try again." },
      400,
    );
  }

  const sourceValue = String(form.get("source") ?? "homepage");
  const source = sourceValue === "download" ? "download" : "homepage";
  const now = new Date().toISOString();

  try {
    await env.SIGNUPS.prepare(
      `INSERT INTO hosted_interest (
         email, created_at, updated_at, consent_version, source, status
       ) VALUES (?, ?, ?, ?, ?, 'active')
       ON CONFLICT(email) DO UPDATE SET
         updated_at = excluded.updated_at,
         consent_version = excluded.consent_version,
         source = excluded.source,
         status = 'active',
         withdrawn_at = NULL`,
    )
      .bind(email, now, now, CONSENT_VERSION, source)
      .run();
  } catch (error) {
    console.error("D1 hosted-interest insert failed", error);
    return responseFor(
      request,
      { ok: false, message: "Signup is temporarily unavailable." },
      503,
    );
  }

  return responseFor(
    request,
    { ok: true, message: "Your interest has been recorded." },
    200,
  );
};

export const ALL: APIRoute = ({ request }) =>
  responseFor(request, { ok: false, message: "Method not allowed." }, 405);
