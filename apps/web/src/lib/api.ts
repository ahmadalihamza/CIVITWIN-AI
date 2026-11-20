import type { FieldError } from "./types";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public fields: FieldError[] = [],
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch("/api/v1" + path, { cache: "no-store", ...init });
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new ApiError(
      response.status,
      error?.code ?? "PLANNER_UNAVAILABLE",
      error?.message ?? "The planner could not process the request. Check that the local API is running.",
      error?.field_errors ?? [],
    );
  }
  return response.json() as Promise<T>;
}

export function post<T>(path: string, body?: unknown, key?: string) {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (key) headers["Idempotency-Key"] = key;
  return api<T>(path, { method: "POST", headers, body: JSON.stringify(body) });
}

export const formatNumber = (value: number) => new Intl.NumberFormat("en-PK").format(value);
export const formatDate = (value: string) =>
  new Intl.DateTimeFormat("en-GB", { dateStyle: "medium", timeZone: "UTC" }).format(new Date(value));
export const errorMessage = (error: unknown) =>
  error instanceof Error ? error.message : "The request could not be completed.";
