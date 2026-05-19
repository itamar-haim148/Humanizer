import type {
  ApiResult,
  DetectRequest,
  DetectResponse,
  HumanizeRequest,
  HumanizeResponse,
} from "./types";

const BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function post<TBody, TResp>(
  path: string,
  body: TBody,
): Promise<ApiResult<TResp>> {
  let res: Response;
  try {
    res = await fetch(`${BASE_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
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
