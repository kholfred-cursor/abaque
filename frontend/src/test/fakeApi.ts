/** A minimal in-memory backend for component tests: routes "METHOD /path" to handlers. */
export type Handler = (request: Request) => Response | Promise<Response>;

export function json(status: number, body?: unknown): Response {
  return body === undefined
    ? new Response(null, { status })
    : new Response(JSON.stringify(body), {
        status,
        headers: { "Content-Type": "application/json" },
      });
}

export function apiError(status: number, code: string): Response {
  return json(status, { error: { code, message: "server message, never displayed" } });
}

export interface FakeApi {
  fetch: typeof globalThis.fetch;
  calls: Request[];
  on: (route: string, handler: Handler) => void;
  count: (route: string) => number;
}

export function fakeApi(routes: Record<string, Handler> = {}): FakeApi {
  const table = new Map(Object.entries(routes));
  const calls: Request[] = [];
  const key = (r: Request) => `${r.method} ${new URL(r.url).pathname}`;
  return {
    calls,
    on: (route, handler) => table.set(route, handler),
    count: (route) => calls.filter((r) => key(r) === route).length,
    fetch: async (input: RequestInfo | URL, init?: RequestInit) => {
      const request = input instanceof Request ? input : new Request(input, init);
      calls.push(request.clone());
      const handler = table.get(key(request));
      return handler ? handler(request) : apiError(404, "NOT_FOUND");
    },
  };
}

export const ME = {
  id: "a1",
  email: "fred@example.com",
  role: "owner" as const,
  email_verified: true,
  organization: { id: "o1", name: "Cabinet Delta", plan_code: "trial" as const },
};
