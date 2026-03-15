import { NextRequest, NextResponse } from "next/server";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export async function POST(
  request: NextRequest,
  context: { params: { sessionId: string } },
) {
  const form = await request.formData();
  const response = await fetch(`${API_BASE}/api/session/${context.params.sessionId}/upload`, {
    method: "POST",
    body: form,
  });

  const text = await response.text();
  return new NextResponse(text, {
    status: response.status,
    headers: {
      "Content-Type": response.headers.get("content-type") ?? "application/json",
    },
  });
}
