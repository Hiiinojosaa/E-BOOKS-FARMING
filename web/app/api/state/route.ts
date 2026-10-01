import { NextResponse } from "next/server";
import { db } from "@/lib/db";
import { currentPartner } from "@/lib/auth";

export async function GET() {
  const partner = await currentPartner();
  if (!partner) return NextResponse.json({ error: "Inicia sesión" }, { status: 401 });
  const { rows } = await db().query("select data from kv_state where id = 'singleton'");
  const data = rows[0]?.data ?? null;
  if (!data) return NextResponse.json({ error: "El motor local todavía no ha sincronizado nada" }, { status: 503 });
  return NextResponse.json({ ...data, me: partner });
}
