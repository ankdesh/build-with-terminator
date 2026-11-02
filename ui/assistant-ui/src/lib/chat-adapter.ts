import type { ChatModelAdapter } from "@assistant-ui/react";

export function createLocalRuntimeAdapter(getUserApiKey?: () => string): ChatModelAdapter {
  return {
    async *run({ messages, abortSignal }) {
      const userApiKey = getUserApiKey ? getUserApiKey() : "";

      const res = await fetch("/api/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          messages: messages.map((m) => ({
            role: m.role,
            content: m.content,
          })),
          userApiKey,
        }),
        signal: abortSignal,
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({ error: "HTTP error " + res.status }));
        throw new Error(errorData.error || `HTTP error ${res.status}`);
      }

      const data = await res.json();
      const contentParts: Array<
        | { type: "text"; text: string }
        | {
            type: "tool-call";
            toolCallId: string;
            toolName: string;
            /* eslint-disable-next-line @typescript-eslint/no-explicit-any */
            args: any;
            argsText: string;
            result?: unknown;
          }
      > = [];

      // Add tool-call parts with required argsText & ReadonlyJSONObject args for assistant-ui
      if (data.toolCalls && data.toolCalls.length > 0) {
        for (const tc of data.toolCalls) {
          contentParts.push({
            type: "tool-call",
            toolCallId: tc.tool_call_id,
            toolName: tc.name,
            /* eslint-disable-next-line @typescript-eslint/no-explicit-any */
            args: tc.args as any,
            argsText: JSON.stringify(tc.args),
            result: tc.result,
          });
        }
      }

      // Add final text response
      if (data.content) {
        contentParts.push({
          type: "text",
          text: data.content,
        });
      }

      yield {
        content: contentParts,
      };
    },
  };
}
