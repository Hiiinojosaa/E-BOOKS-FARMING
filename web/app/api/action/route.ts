import { NextRequest, NextResponse } from "next/server";
import { db } from "@/lib/db";
import { currentPartner } from "@/lib/auth";

function sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}

export async function POST(req: NextRequest) {
  if (req.headers.get("x-ebf") !== "1") return NextResponse.json({ error: "petición rechazada" }, { status: 403 });
  const partner = await currentPartner();
  if (!partner) return NextResponse.json({ error: "Inicia sesión" }, { status: 401 });
  const payload = await req.json().catch(() => ({}));
  const id = crypto.randomUUID();
  await db().query("insert into pending_actions (id, partner, payload) values ($1,$2,$3)", [id, partner, payload]);

  // Short-poll: the local engine picks this up within a few seconds and marks it done/error.
  for (let i = 0; i < 24; i++) {
    await sleep(400);
    const { rows } = await db().query("select status, result, error from pending_actions where id = $1", [id]);
    const row = rows[0];
    if (!row) break;
    if (row.status === "done") return NextResponse.json({ ok: true, result: row.result });
    if (row.status === "error") return NextResponse.json({ error: row.error || "Error en el motor local" }, { status: 400 });
  }
  return NextResponse.json({ ok: true, queued: true });
}
