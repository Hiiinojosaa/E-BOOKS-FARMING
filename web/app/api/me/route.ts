import { NextResponse } from "next/server";
import { db } from "@/lib/db";
import { currentPartner } from "@/lib/auth";

export async function GET() {
  const partner = await currentPartner();
  const { rows: stateRows } = await db().query("select data from kv_state where id = 'singleton'");
  const names: Record<string, string> = stateRows[0]?.data?.names ?? { ADMIN: "Addless Motions" };
  const { rows: userRows } = await db().query("select partner from users");
  const known = new Set(userRows.map((r) => r.partner));
  const profiles = Object.entries(names).map(([id, name]) => ({ id, name, has_pin: known.has(id) }));
  return NextResponse.json({ partner, name: partner ? names[partner] : null, profiles });
}
