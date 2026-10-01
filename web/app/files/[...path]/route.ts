import { NextRequest, NextResponse } from "next/server";
import { db } from "@/lib/db";
import { currentPartner } from "@/lib/auth";

// Mirrors the local panel's /files/BOOKS/<id>/... convention, but reads bytes mirrored into
// Postgres (book_files) instead of the local disk, which this serverless function can't see.
export async function GET(_req: NextRequest, ctx: RouteContext<"/files/[...path]">) {
  const partner = await currentPartner();
  if (!partner) return NextResponse.json({ error: "Inicia sesión" }, { status: 401 });
  const { path: parts } = await ctx.params;
  if (parts[0] !== "BOOKS" || parts.length < 2) return NextResponse.json({ error: "no encontrado" }, { status: 404 });
  const bookId = parts[1];
  const rest = parts.slice(2).join("/");
  const kind = rest === "design/cover.png" ? "cover" : rest.endsWith(".pdf") ? "pdf" : rest.endsWith(".epub") ? "epub" : null;
  if (!kind) return NextResponse.json({ error: "no encontrado" }, { status: 404 });

  const { rows } = await db().query(
    "select filename, content_type, data from book_files where book_id = $1 and kind = $2",
    [bookId, kind],
  );
  if (!rows[0]) return NextResponse.json({ error: "no encontrado" }, { status: 404 });
  const { content_type, data } = rows[0];
  return new NextResponse(data, { headers: { "Content-Type": content_type, "Cache-Control": "no-store" } });
}
