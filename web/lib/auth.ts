import crypto from "crypto";
import { cookies } from "next/headers";
import { db } from "./db";

const SESSION_HOURS = 12;
const COOKIE = "ebf_session";

export function hashPin(pin: string, saltHex: string): string {
  return crypto.pbkdf2Sync(pin, Buffer.from(saltHex, "hex"), 200_000, 32, "sha256").toString("hex");
}

export async function login(partner: string, pin: string): Promise<string> {
  const { rows } = await db().query("select partner, salt, pin_hash from users where partner = $1", [partner]);
  const u = rows[0];
  if (!u) throw new Error("Esta cuenta aún no se ha sincronizado desde el panel local. Entra una vez allí y vuelve a intentarlo.");
  if (!crypto.timingSafeEqual(Buffer.from(u.pin_hash, "hex"), Buffer.from(hashPin(pin, u.salt), "hex"))) {
    throw new Error("Contraseña incorrecta");
  }
  const token = crypto.randomBytes(32).toString("base64url");
  const expires = new Date(Date.now() + SESSION_HOURS * 3600 * 1000);
  await db().query("insert into sessions (token, partner, expires_at) values ($1,$2,$3)", [token, partner, expires]);
  return token;
}

export async function logout(token: string | undefined) {
  if (token) await db().query("delete from sessions where token = $1", [token]);
}

export async function currentPartner(): Promise<string | null> {
  const token = (await cookies()).get(COOKIE)?.value;
  if (!token) return null;
  const { rows } = await db().query("select partner from sessions where token = $1 and expires_at > now()", [token]);
  return rows[0]?.partner ?? null;
}

export function sessionCookie(token: string) {
  return { name: COOKIE, value: token, httpOnly: true, sameSite: "strict" as const, path: "/", maxAge: SESSION_HOURS * 3600 };
}

export const SESSION_COOKIE_NAME = COOKIE;
