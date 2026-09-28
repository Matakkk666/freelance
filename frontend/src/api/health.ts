import { ApiError, apiGet } from "./client.ts";

/** Mirrors backend/app/api/health.py::HealthResponse. */
export interface HealthResponse {
  status: "ok" | "error";
  database: "ok" | "unavailable";
}

export async function fetchHealth(signal?: AbortSignal): Promise<HealthResponse> {
  try {
    return await apiGet<HealthResponse>("/health", signal ? { signal } : undefined);
  } catch (error) {
    // 503 still carries a valid health body.
    if (error instanceof ApiError && error.status === 503 && error.body) {
      return error.body as HealthResponse;
    }
    throw error;
  }
}
