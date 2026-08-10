import { NextRequest, NextResponse } from "next/server";
import OpenAI from "openai";
import { TOOLS_SPECIFICATIONS } from "@/lib/tools";
import { executeHttpToolByName } from "@/lib/http-tool-executor";

export const runtime = "nodejs";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { messages, userApiKey } = body;

    // Retrieve API key: from user override or environment variable
    const apiKey = userApiKey || process.env.OPENAI_API_KEY || process.env.NEXT_PUBLIC_OPENAI_API_KEY;

    if (!apiKey) {
      return NextResponse.json(
        {
          error: "OPENAI_API_KEY environment variable is missing. Please set OPENAI_API_KEY in .env.local or enter it in the header.",
        },
        { status: 401 }
      );
    }

    const openai = new OpenAI({ apiKey });

    // Format messages for OpenAI API
    const formattedMessages: OpenAI.Chat.ChatCompletionMessageParam[] = messages.map(
      (m: { role: string; content: string | unknown[]; tool_call_id?: string; tool_calls?: unknown[] }) => {
        if (m.role === "tool") {
          return {
            role: "tool",
            tool_call_id: m.tool_call_id || "",
            content: typeof m.content === "string" ? m.content : JSON.stringify(m.content),
          };
        }
        
        let textContent = "";
        if (typeof m.content === "string") {
          textContent = m.content;
        } else if (Array.isArray(m.content)) {
          textContent = m.content
            .filter((c: unknown) => (c as { type?: string }).type === "text")
            .map((c: unknown) => (c as { text?: string }).text || "")
            .join("\n");
        }

        return {
          role: m.role as "user" | "assistant" | "system",
          content: textContent,
        };
      }
    );

    // Initial OpenAI API call with tools
    const response = await openai.chat.completions.create({
      model: "gpt-4o-mini",
      messages: formattedMessages,
      tools: TOOLS_SPECIFICATIONS as OpenAI.Chat.ChatCompletionTool[],
      tool_choice: "auto",
      stream: false,
    });

    const choice = response.choices[0];
    const assistantMsg = choice.message;

    // Check if model decided to invoke external HTTP tools
    if (assistantMsg.tool_calls && assistantMsg.tool_calls.length > 0) {
      const toolCallResults = [];

      for (const toolCall of assistantMsg.tool_calls) {
        if (toolCall.type === "function") {
          const toolName = toolCall.function.name;
          const args = JSON.parse(toolCall.function.arguments || "{}");

          // Execute External HTTP REST API Request
          const toolResult = await executeHttpToolByName(toolName, args);

          toolCallResults.push({
            tool_call_id: toolCall.id,
            name: toolName,
            args,
            result: toolResult,
          });
        }
      }

      // Append assistant tool_calls and tool results to messages loop
      const updatedMessages: OpenAI.Chat.ChatCompletionMessageParam[] = [
        ...formattedMessages,
        assistantMsg,
        ...toolCallResults.map((t) => ({
          role: "tool" as const,
          tool_call_id: t.tool_call_id,
          content: JSON.stringify(t.result),
        })),
      ];

      // Second call to OpenAI with tool results to generate final response
      const finalCompletion = await openai.chat.completions.create({
        model: "gpt-4o-mini",
        messages: updatedMessages,
      });

      const finalContent = finalCompletion.choices[0].message.content || "";

      return NextResponse.json({
        content: finalContent,
        toolCalls: toolCallResults,
      });
    }

    // Direct text response without tool calls
    return NextResponse.json({
      content: assistantMsg.content || "",
      toolCalls: [],
    });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err);
    console.error("Error in /api/chat route:", message);
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
