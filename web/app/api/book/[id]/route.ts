import { NextRequest, NextResponse } from "next/server";
import { db } from "@/lib/db";
import { currentPartner } from "@/lib/auth";

export async function GET(_req: NextRequest, ctx: RouteContext<"/api/book/[id]">) {
  const partner = await currentPartner();
  if (!partner) return NextResponse.json({ error: "Inicia sesión" }, { status: 401 });
  const { id } = await ctx.params;
  const { rows } = await db().query("select data from book_details where book_id = $1", [id]);
  if (!rows[0]) return NextResponse.json({ error: "Libro no encontrado" }, { status: 404 });
  return NextResponse.json(rows[0].data);
}
