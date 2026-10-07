/**
 * ChattamAI Edge API Gateway & Reverse Proxy
 * Cloudflare Worker for routing edge traffic to the containerized backend.
 *
 * Responsibilities:
 * - Dynamic CORS negotiation for Vercel frontend deployments
 * - Preflight (OPTIONS) caching and response
 * - Reverse-proxying /api/* and /auth/* to the container backend
 * - Edge health-check endpoint (/cf-health)
 * - Security header injection
 */

const DEFAULT_ALLOWED_ORIGINS = [
  "http://localhost:5173",
  "http://127.0.0.1:5173",
];

function getCorsHeaders(request, env) {
  const origin = request.headers.get("Origin") || "";
  const allowedList = (env.ALLOWED_ORIGINS || "")
    .split(",")
    .map((o) => o.trim())
    .filter(Boolean)
    .concat(DEFAULT_ALLOWED_ORIGINS);

  // If Vercel preview URLs (*.vercel.app) or configured domains match
  const isAllowed =
    allowedList.includes(origin) ||
    origin.endsWith(".vercel.app") ||
    origin === env.FRONTEND_ORIGIN;

  const allowOrigin = isAllowed ? origin : allowedList[0] || "*";

  return {
    "Access-Control-Allow-Origin": allowOrigin,
    "Access-Control-Allow-Methods": "GET, POST, PUT, PATCH, DELETE, OPTIONS",
    "Access-Control-Allow-Headers":
      "Content-Type, Authorization, X-Admin-Key, Accept, Origin, X-Requested-With",
    "Access-Control-Allow-Credentials": "true",
    "Access-Control-Max-Age": "86400",
  };
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const corsHeaders = getCorsHeaders(request, env);

    // 1. Edge Preflight handling
    if (request.method === "OPTIONS") {
      return new Response(null, {
        status: 204,
        headers: {
          ...corsHeaders,
          "Content-Length": "0",
        },
      });
    }

    // 2. Edge Health Check endpoint
    if (url.pathname === "/cf-health") {
      return new Response(
        JSON.stringify({
          status: "ok",
          service: "ChattamAI Cloudflare Edge Gateway",
          timestamp: new Date().toISOString(),
          backend_origin: env.BACKEND_ORIGIN || "not_configured",
        }),
        {
          status: 200,
          headers: {
            "Content-Type": "application/json",
            ...corsHeaders,
          },
        }
      );
    }

    // 3. Resolve target backend URL
    const backendOrigin = env.BACKEND_ORIGIN;
    if (!backendOrigin) {
      return new Response(
        JSON.stringify({
          error: "BACKEND_ORIGIN environment variable is not configured on Cloudflare Worker.",
        }),
        {
          status: 502,
          headers: {
            "Content-Type": "application/json",
            ...corsHeaders,
          },
        }
      );
    }

    const targetUrl = new URL(url.pathname + url.search, backendOrigin);

    // 4. Forward headers
    const forwardHeaders = new Headers(request.headers);
    forwardHeaders.set("X-Forwarded-Host", url.host);
    forwardHeaders.set("X-Forwarded-Proto", url.protocol.replace(":", ""));
    forwardHeaders.set(
      "X-Forwarded-For",
      request.headers.get("CF-Connecting-IP") ||
        request.headers.get("X-Forwarded-For") ||
        ""
    );

    // Forward the request to container backend
    try {
      const backendResponse = await fetch(targetUrl.toString(), {
        method: request.method,
        headers: forwardHeaders,
        body: ["GET", "HEAD"].includes(request.method) ? null : request.body,
        redirect: "follow",
      });

      // 5. Merge backend response headers with edge CORS & security headers
      const responseHeaders = new Headers(backendResponse.headers);
      Object.entries(corsHeaders).forEach(([k, v]) => {
        responseHeaders.set(k, v);
      });
      responseHeaders.set("X-Content-Type-Options", "nosniff");
      responseHeaders.set("X-Frame-Options", "DENY");
      responseHeaders.set("Referrer-Policy", "strict-origin-when-cross-origin");

      return new Response(backendResponse.body, {
        status: backendResponse.status,
        statusText: backendResponse.statusText,
        headers: responseHeaders,
      });
    } catch (err) {
      return new Response(
        JSON.stringify({
          error: "Failed to connect to backend container origin.",
          detail: err.message,
        }),
        {
          status: 502,
          headers: {
            "Content-Type": "application/json",
            ...corsHeaders,
          },
        }
      );
    }
  },
};
