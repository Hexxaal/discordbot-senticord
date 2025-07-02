const sqlite3 = require('sqlite3').verbose();
const db = new sqlite3.Database(process.env.SQLITE_DB_PATH||'senticord.db');

db.serialize(() => {
  db.run(`CREATE TABLE IF NOT EXISTS pending_captchas (
    member_id TEXT PRIMARY KEY,
    guild_id TEXT,
    code TEXT,
    attempts INTEGER,
    created TEXT
  )`);
  db.run(`CREATE TABLE IF NOT EXISTS guild_settings (
    guild_id TEXT PRIMARY KEY,
    admin_role TEXT,
    log_channel TEXT
  )`);
});
db.close();
