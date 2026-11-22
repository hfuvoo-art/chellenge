// Пересоздать базу с вымышленными данными: npm run seed
import fs from "node:fs";
import path from "node:path";

const file = process.env.DATABASE_PATH || path.join(process.cwd(), "data", "dekanat.db");
for (const f of [file, `${file}-wal`, `${file}-shm`]) if (fs.existsSync(f)) fs.rmSync(f);
const { getDb } = await import("../lib/db.ts");
const db = getDb();
const n = (db.prepare("SELECT COUNT(*) n FROM users").get() as { n: number }).n;
console.log(`База пересоздана: ${file}, пользователей: ${n}`);
