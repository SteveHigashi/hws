// Server-Sent Events over fetch, so the token travels in a header.
//
// EventSource cannot set request headers, so the only way to authenticate it is to put
// the credential in the URL. That is what this app did, and on 2026-09-23 a live admin
// JWT — valid for another 26 days — was sitting in plaintext in journald and would have
// been in the nginx access log, browser history and any proxy in between. It also never
// worked: the endpoint only ever read the Authorization header, so every connection was
// a 401 and the Real-time feed had simply been dead.
//
// fetch can set headers and its body is a stream, so the same SSE response parses fine
// with none of that. Nothing secret goes in a URL.

const FRAME = /\r?\n\r?\n/;

/**
 * Open an SSE stream and call onMessage with each `data:` payload (already JSON-parsed).
 * Returns a function that closes it. Reconnects with backoff until closed.
 */
export function openEventStream(url, { token, onMessage, onOpen, onError } = {}) {
  let closed = false;
  let controller = null;
  let attempt = 0;
  let timer = null;

  const run = async () => {
    if (closed) return;
    controller = new AbortController();
    try {
      const response = await fetch(url, {
        headers: { Authorization: `Bearer ${token}`, Accept: "text/event-stream" },
        signal: controller.signal,
        cache: "no-store",
      });
      if (!response.ok || !response.body) throw new Error(`stream ${response.status}`);

      attempt = 0;
      onOpen?.();

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (!closed) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        let split = buffer.split(FRAME);
        buffer = split.pop() ?? "";
        for (const frame of split) {
          const data = frame
            .split(/\r?\n/)
            .filter((line) => line.startsWith("data:"))
            .map((line) => line.slice(5).trim())
            .join("\n");
          if (!data) continue;
          try {
            onMessage?.(JSON.parse(data));
          } catch (_) {
            // a half-written frame is not worth killing the stream over
          }
        }
      }
    } catch (err) {
      if (closed || err?.name === "AbortError") return;
      onError?.(err);
    }
    if (closed) return;
    onError?.();
    // Back off so a dead endpoint does not become a request loop: 2s, 4s, 8s … 30s.
    attempt += 1;
    timer = setTimeout(run, Math.min(30000, 2000 * 2 ** (attempt - 1)));
  };

  run();

  return () => {
    closed = true;
    clearTimeout(timer);
    controller?.abort();
  };
}

export default openEventStream;
