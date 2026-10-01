import { NextRequest, NextResponse } from "next/server";
import { login, sessionCookie } from "@/lib/auth";

export async function POST(req: NextRequest) {
  try {
    const { partner, pin } = await req.json();
    if (!partner || !pin) return NextResponse.json({ error: "Faltan datos" }, { status: 400 });
    const token = await login(String(partner), String(pin));
    const res = NextResponse.json({ ok: true });
    res.cookies.set(sessionCookie(token));
    return res;
  } catch (e: unknown) {
    return NextResponse.json({ error: e instanceof Error ? e.message : "Error" }, { status: 400 });
  }
}
