import type {
  ApiResult,
  DetectRequest,
  DetectResponse,
  HumanizeLLMResponse,
  HumanizeRequest,
  HumanizeResponse,
} from "./types";

// Always use same-origin so requests go through the Next.js rewrite to the
// internal API. Embedding a base URL via NEXT_PUBLIC_API_BASE_URL at build
// time can leak internal hostnames (e.g. http://api:8000) into the browser
// bundle and cause mixed-content failures on HTTPS deployments.
const BASE_URL = "";

async function post<TBody, TResp>(
  path: string,
  body: TBody,
  extraHeaders?: Record<string, string>,
): Promise<ApiResult<TResp>> {
  let res: Response;
  try {
    res = await fetch(`${BASE_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...(extraHeaders ?? {}) },
      body: JSON.stringify(body),
      cache: "no-store",
    });
  } catch (err) {
    return {
      ok: false,
      status: 0,
      message: err instanceof Error ? err.message : "network_error",
    };
  }

  if (!res.ok) {
    let detail: unknown;
    try {
      detail = await res.json();
    } catch {
      detail = await res.text().catch(() => undefined);
    }
    return {
      ok: false,
      status: res.status,
      message: `http_${res.status}`,
      detail,
    };
  }

  const data = (await res.json()) as TResp;
  return { ok: true, data };
}

export function humanize(
  req: HumanizeRequest,
): Promise<ApiResult<HumanizeResponse>> {
  return post("/api/humanize", req);
}

export function detect(req: DetectRequest): Promise<ApiResult<DetectResponse>> {
  return post("/api/detect", req);
}

/**
 * Encodes `user:password` as a Basic auth header value.
 * Uses btoa (browser) — safe for ASCII; for unicode user/pass would need a
 * TextEncoder pass, but the LLM gate is single-user with ASCII credentials.
 */
export function makeBasicAuth(user: string, password: string): string {
  return `Basic ${btoa(`${user}:${password}`)}`;
}

export function humanizeLLM(
  req: HumanizeRequest,
  basicAuth: string,
): Promise<ApiResult<HumanizeLLMResponse>> {
  return post("/api/humanize/llm", req, { Authorization: basicAuth });
}
