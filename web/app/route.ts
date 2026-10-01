import fs from "fs";
import path from "path";

export async function GET() {
  const html = fs.readFileSync(path.join(process.cwd(), "panel-src.html"), "utf-8");
  return new Response(html, { headers: { "content-type": "text/html; charset=utf-8" } });
}
