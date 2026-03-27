/**
 * Brigade API Client — TypeScript HTTP wrapper для Python brigade pipeline
 *
 * Позволяет TypeScript-части OpenClaw вызывать brigade-пайплайн как REST API.
 * Сервер запускается Python-ботом на порту 8765 (BRIGADE_API_PORT).
 *
 * @example
 * ```ts
 * import { BrigadeClient } from "./brigade-client.js";
 *
 * const client = new BrigadeClient();
 * const result = await client.execute({ prompt: "Проверь цену AK-47 Redline", brigade: "Dmarket" });
 * console.log(result.final_response);
 * ```
 */

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type BrigadeExecuteRequest = {
  /** Промпт для агентов */
  prompt: string;
  /** Название бригады: "Dmarket" | "OpenClaw" */
  brigade?: string;
  /** Максимум шагов в цепочке (1–10) */
  max_steps?: number;
  /** Тип задачи (override цепочки) */
  task_type?: string | null;
};

export type BrigadeStepResult = {
  role: string;
  model: string;
  response: string;
  duration_ms: number;
};

export type BrigadeExecuteResponse = {
  final_response: string;
  brigade: string;
  chain_executed: string[];
  steps: BrigadeStepResult[];
  status: "completed" | "ask_user" | (string & {});
  question?: string | null;
  duration_ms: number;
};

export type BrigadeInfo = {
  name: string;
  description: string;
  workspace_dir: string;
  roles: string[];
  pipeline: string[];
};

export type BrigadeStatus = {
  ok: boolean;
  version: string;
  ollama_url: string;
  ollama_reachable: boolean;
  brigades: string[];
  uptime_sec: number;
};

/** События от SSE-стрима /brigade/execute/stream */
export type BrigadeStreamEvent =
  | { type: "step"; role: string; model: string; text: string }
  | { type: "done"; final_response: string; chain_executed: string[]; status: string }
  | { type: "error"; message: string };

// ---------------------------------------------------------------------------
// Error
// ---------------------------------------------------------------------------

export class BrigadeApiError extends Error {
  constructor(
    message: string,
    public readonly statusCode: number,
    public readonly detail?: string,
  ) {
    super(message);
    this.name = "BrigadeApiError";
  }
}

// ---------------------------------------------------------------------------
// Client
// ---------------------------------------------------------------------------

export type BrigadeClientOptions = {
  /** Base URL of the brigade API server (default: http://127.0.0.1:8765) */
  baseUrl?: string;
  /** Request timeout in milliseconds (default: 300_000 = 5 min) */
  timeoutMs?: number;
  /** Retry attempts on network error (default: 2) */
  retries?: number;
};

export class BrigadeClient {
  private readonly baseUrl: string;
  private readonly timeoutMs: number;
  private readonly retries: number;

  constructor(options: BrigadeClientOptions = {}) {
    const port = process.env.BRIGADE_API_PORT ?? "8765";
    this.baseUrl = options.baseUrl ?? `http://127.0.0.1:${port}`;
    this.timeoutMs = options.timeoutMs ?? 300_000;
    this.retries = options.retries ?? 2;
  }

  /** Execute a brigade pipeline and return the final result. */
  async execute(req: BrigadeExecuteRequest): Promise<BrigadeExecuteResponse> {
    const body: BrigadeExecuteRequest = {
      brigade: "Dmarket",
      max_steps: 5,
      ...req,
    };
    return this._post<BrigadeExecuteResponse>("/brigade/execute", body);
  }

  /** Stream pipeline step updates via SSE. Calls onEvent for each step. */
  async executeStream(
    req: BrigadeExecuteRequest,
    onEvent: (event: BrigadeStreamEvent) => void,
  ): Promise<void> {
    const url = `${this.baseUrl}/brigade/execute/stream`;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);

    try {
      const resp = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(req),
        signal: controller.signal,
      });

      if (!resp.ok) {
        const text = await resp.text().catch(() => "");
        throw new BrigadeApiError(`Brigade API error ${resp.status}`, resp.status, text);
      }

      if (!resp.body) {
        throw new BrigadeApiError("No response body for SSE stream", 500);
      }

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) {
          break;
        }
        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) {
            continue;
          }
          try {
            const event = JSON.parse(line.slice(6)) as BrigadeStreamEvent;
            onEvent(event);
          } catch {
            // skip malformed SSE line
          }
        }
      }
    } finally {
      clearTimeout(timer);
    }
  }

  /** List all available brigades with their roles and pipeline. */
  async listBrigades(): Promise<BrigadeInfo[]> {
    return this._get<BrigadeInfo[]>("/brigade/brigades");
  }

  /** Check brigade API health and Ollama connectivity. */
  async status(): Promise<BrigadeStatus> {
    return this._get<BrigadeStatus>("/brigade/status");
  }

  /** Returns true if the brigade API server is reachable. */
  async isReachable(): Promise<boolean> {
    try {
      const s = await this.status();
      return s.ok;
    } catch {
      return false;
    }
  }

  // ---------------------------------------------------------------------------
  // Private helpers
  // ---------------------------------------------------------------------------

  private async _get<T>(path: string): Promise<T> {
    return this._request<T>("GET", path);
  }

  private async _post<T>(path: string, body: unknown): Promise<T> {
    return this._request<T>("POST", path, body);
  }

  private async _request<T>(method: string, path: string, body?: unknown): Promise<T> {
    let lastError: unknown;

    for (let attempt = 0; attempt <= this.retries; attempt++) {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), this.timeoutMs);

      try {
        const init: RequestInit = {
          method,
          signal: controller.signal,
          headers: { "Content-Type": "application/json" },
        };
        if (body !== undefined) {
          init.body = JSON.stringify(body);
        }

        const resp = await fetch(`${this.baseUrl}${path}`, init);

        if (!resp.ok) {
          let detail: string | undefined;
          try {
            const err = (await resp.json()) as { detail?: string };
            detail = err.detail;
          } catch {
            detail = await resp.text().catch(() => undefined);
          }
          throw new BrigadeApiError(
            `Brigade API responded with ${resp.status} ${resp.statusText}`,
            resp.status,
            detail,
          );
        }

        return (await resp.json()) as T;
      } catch (err) {
        lastError = err;
        if (err instanceof BrigadeApiError) {
          throw err;
        } // don't retry HTTP errors
        if (attempt < this.retries) {
          await _sleep(300 * (attempt + 1));
        }
      } finally {
        clearTimeout(timer);
      }
    }

    throw lastError;
  }
}

function _sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// ---------------------------------------------------------------------------
// Singleton
// ---------------------------------------------------------------------------

let _defaultClient: BrigadeClient | null = null;

/** Get the default brigade client (singleton, lazy-initialized). */
export function getBrigadeClient(options?: BrigadeClientOptions): BrigadeClient {
  if (!_defaultClient || options) {
    _defaultClient = new BrigadeClient(options);
  }
  return _defaultClient;
}
