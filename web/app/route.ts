import fs from "fs";
import path from "path";

const html = fs.readFileSync(path.join(process.cwd(), "panel-src.html"), "utf-8");

export async function GET() {
  return new Response(html, { headers: { "content-type": "text/html; charset=utf-8" } });
}
