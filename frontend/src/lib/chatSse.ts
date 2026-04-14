/** Parse `text/event-stream` lines (`data: {...}\\n\\n`). */

export type SseChatEvent =
  | { type: "delta"; text: string }
  | {
      type: "done";
      citations: Citation[];
      confidence: string;
      assistant_message_id: string;
      user_message_id: string;
      generation_mode?: string;
      generation_model?: string | null;
    }
  | { type: "error"; detail: string };

export type Citation = {
  chunk_id: string;
  document_id: string;
  document_filename: string;
  chunk_index: number;
  page_number: number | null;
  score: number;
  quote: string;
};

export async function* streamChatSse(
  url: string,
  body: Record<string, unknown>,
  token: string | null,
): AsyncGenerator<SseChatEvent> {
  const res = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
  });

  if (!res.ok || !res.body) {
    const t = await res.text();
    yield { type: "error", detail: t || res.statusText };
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const parts = buf.split("\n\n");
    buf = parts.pop() ?? "";
    for (const block of parts) {
      const line = block.trim();
      if (!line.startsWith("data:")) continue;
      const json = line.slice(5).trim();
      try {
        const obj = JSON.parse(json) as SseChatEvent;
        yield obj;
      } catch {
        /* ignore partial */
      }
    }
  }
  const tail = buf.trim();
  if (tail.startsWith("data:")) {
    const json = tail.slice(5).trim();
    try {
      yield JSON.parse(json) as SseChatEvent;
    } catch {
      /* ignore */
    }
  }
}
