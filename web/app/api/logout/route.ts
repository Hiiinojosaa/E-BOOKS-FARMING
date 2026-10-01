import { NextRequest, NextResponse } from "next/server";
import { logout, SESSION_COOKIE_NAME } from "@/lib/auth";

export async function POST(req: NextRequest) {
  await logout(req.cookies.get(SESSION_COOKIE_NAME)?.value);
  const res = NextResponse.json({ ok: true });
  res.cookies.set({ name: SESSION_COOKIE_NAME, value: "", path: "/", maxAge: 0 });
  return res;
}
