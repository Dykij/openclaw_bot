/**
 * Brigade Hook Handler — интеграция Brigade API в OpenClaw HTTP gateway
 *
 * Обрабатывает HTTP-запросы по пути /brigade/* поступающие в OpenClaw gateway.
 * Проксирует запросы в Python Brigade REST API (порт 8765).
 *
 * Использование в server-http.ts:
 * ```ts
 * const brigadeHandler = createBrigadeHttpHandler(config);
 * // в цепочке обработчиков:
 * if (await brigadeHandler(req, res, requestPath)) return;
 * ```
 *
 * Конфигурация (openclaw.json / OpenClawConfig):
 * ```json
 * {
 *   "brigade": {
 *     "enabled": true,
 *     "apiUrl": "http://127.0.0.1:8765",
 *     "token": "your-secret-token"   // опционально
 *   }
 * }
 * ```
 */

import type { IncomingMessage, ServerResponse } from "node:http";
import {
    BrigadeApiError,
    BrigadeClient,
    type BrigadeExecuteRequest,
    type BrigadeStreamEvent,
} from "../brigade-client.js";

const BRIGADE_PREFIX = "/brigade";
const DEFAULT_BRIGADE_API_URL = `http://127.0.0.1:${process.env.BRIGADE_API_PORT ?? "8765"}`;
const MAX_BODY_BYTES = 256 * 1024; // 256 KB

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type BrigadeHttpHandlerConfig = {
  /** URL к Python Brigade API (default: http://127.0.0.1:8765) */
  apiUrl?: string;
  /** Если задан — требовать Bearer токен на входящих запросах */
  token?: string;
  /** Таймаут ожидания ответа от Brigade API (ms, default: 300_000) */
  timeoutMs?: number;
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function sendJson(res: ServerResponse, status: number, body: unknown): void {
  const payload = JSON.stringify(body);
  res.statusCode = status;
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  res.setHeader("Content-Length", Buffer.byteLength(payload));
  res.end(payload);
}

function sendError(res: ServerResponse, status: number, message: string): void {
  sendJson(res, status, { error: { message, type: "brigade_error" } });
}

async function readBody(req: IncomingMessage, maxBytes: number): Promise<string> {
  return new Promise((resolve, reject) => {
    let data = "";
    let size = 0;

    req.on("data", (chunk: Buffer) => {
      size += chunk.length;
      if (size > maxBytes) {
        reject(new Error(`Request body exceeds ${maxBytes} bytes`));
        return;
      }
      data += chunk.toString("utf8");
    });

    req.on("end", () => resolve(data));
    req.on("error", reject);
  });
}

// ---------------------------------------------------------------------------
// Handler factory
// ---------------------------------------------------------------------------

/**
 * Creates an HTTP handler function for /brigade/* routes.
 * Returns `true` if the request was handled (caller should stop pipeline).
 */
export function createBrigadeHttpHandler(
  cfg: BrigadeHttpHandlerConfig = {},
): (req: IncomingMessage, res: ServerResponse, requestPath: string) => Promise<boolean> {
  const client = new BrigadeClient({
    baseUrl: cfg.apiUrl ?? DEFAULT_BRIGADE_API_URL,
    timeoutMs: cfg.timeoutMs ?? 300_000,
  });

  return async function handleBrigadeRequest(
    req: IncomingMessage,
    res: ServerResponse,
    requestPath: string,
  ): Promise<boolean> {
    if (!requestPath.startsWith(BRIGADE_PREFIX)) return false;

    const method = (req.method ?? "GET").toUpperCase();

    // Optional Bearer token check
    if (cfg.token) {
      const authHeader = req.headers.authorization ?? "";
      const provided = authHeader.startsWith("Bearer ") ? authHeader.slice(7).trim() : "";
      if (provided !== cfg.token) {
        sendError(res, 401, "Unauthorized: invalid or missing brigade token");
        return true;
      }
    }

    // ------------------------------------------------------------------
    // Route: GET /brigade/status
    // ------------------------------------------------------------------
    if (requestPath === "/brigade/status" && method === "GET") {
      try {
        const status = await client.status();
        sendJson(res, 200, status);
      } catch (err) {
        sendError(res, 503, `Brigade API unreachable: ${String(err)}`);
      }
      return true;
    }

    // ------------------------------------------------------------------
    // Route: GET /brigade/brigades
    // ------------------------------------------------------------------
    if (requestPath === "/brigade/brigades" && (method === "GET" || method === "HEAD")) {
      if (method === "HEAD") {
        res.statusCode = 200;
        res.end();
        return true;
      }
      try {
        const brigades = await client.listBrigades();
        sendJson(res, 200, brigades);
      } catch (err) {
        sendError(res, 503, `Brigade list failed: ${String(err)}`);
      }
      return true;
    }

    // ------------------------------------------------------------------
    // Route: POST /brigade/execute
    // ------------------------------------------------------------------
    if (requestPath === "/brigade/execute" && method === "POST") {
      let body: string;
      try {
        body = await readBody(req, MAX_BODY_BYTES);
      } catch {
        sendError(res, 413, "Request body too large");
        return true;
      }

      let parsed: Partial<BrigadeExecuteRequest>;
      try {
        parsed = JSON.parse(body) as Partial<BrigadeExecuteRequest>;
      } catch {
        sendError(res, 400, "Invalid JSON body");
        return true;
      }

      if (!parsed.prompt || typeof parsed.prompt !== "string") {
        sendError(res, 400, "Missing required field: prompt");
        return true;
      }

      try {
        const result = await client.execute({
          prompt: parsed.prompt,
          brigade: parsed.brigade ?? "Dmarket",
          max_steps: parsed.max_steps,
          task_type: parsed.task_type,
        });
        sendJson(res, 200, result);
      } catch (err) {
        if (err instanceof BrigadeApiError) {
          sendError(res, err.statusCode >= 400 ? err.statusCode : 502, err.message);
        } else {
          sendError(res, 502, `Brigade execution failed: ${String(err)}`);
        }
      }
      return true;
    }

    // ------------------------------------------------------------------
    // Route: POST /brigade/execute/stream  — SSE
    // ------------------------------------------------------------------
    if (requestPath === "/brigade/execute/stream" && method === "POST") {
      let body: string;
      try {
        body = await readBody(req, MAX_BODY_BYTES);
      } catch {
        sendError(res, 413, "Request body too large");
        return true;
      }

      let parsed: Partial<BrigadeExecuteRequest>;
      try {
        parsed = JSON.parse(body) as Partial<BrigadeExecuteRequest>;
      } catch {
        sendError(res, 400, "Invalid JSON body");
        return true;
      }

      if (!parsed.prompt || typeof parsed.prompt !== "string") {
        sendError(res, 400, "Missing required field: prompt");
        return true;
      }

      // Set up SSE headers
      res.statusCode = 200;
      res.setHeader("Content-Type", "text/event-stream; charset=utf-8");
      res.setHeader("Cache-Control", "no-cache");
      res.setHeader("Connection", "keep-alive");
      res.setHeader("X-Accel-Buffering", "no");
      res.flushHeaders();

      const writeEvent = (data: BrigadeStreamEvent) => {
        if (!res.writableEnded) {
          res.write(`data: ${JSON.stringify(data)}\n\n`);
        }
      };

      try {
        await client.executeStream(
          {
            prompt: parsed.prompt,
            brigade: parsed.brigade ?? "Dmarket",
            max_steps: parsed.max_steps,
            task_type: parsed.task_type,
          },
          writeEvent,
        );
      } catch (err) {
        writeEvent({ type: "error", message: String(err) });
      } finally {
        res.end();
      }
      return true;
    }

    // Unknown /brigade/* path
    sendError(res, 404, `Brigade route not found: ${requestPath}`);
    return true;
  };
}
