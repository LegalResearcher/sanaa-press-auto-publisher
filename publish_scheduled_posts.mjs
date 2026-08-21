const supabaseUrl = process.env.SUPABASE_URL?.replace(/\/$/, "");
const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY;

if (!supabaseUrl || !serviceRoleKey) {
  throw new Error("SUPABASE_URL وSUPABASE_SERVICE_ROLE_KEY مطلوبان لتشغيل النشر المجدول.");
}

const response = await fetch(`${supabaseUrl}/rest/v1/rpc/publish_due_scheduled_posts`, {
  method: "POST",
  headers: {
    apikey: serviceRoleKey,
    Authorization: `Bearer ${serviceRoleKey}`,
    "Content-Type": "application/json",
  },
  body: "{}",
});

if (!response.ok) {
  throw new Error(`تعذر تنفيذ النشر المجدول: ${response.status} ${await response.text()}`);
}

const published = await response.json();
console.log(JSON.stringify({ ok: true, published, completedAt: new Date().toISOString() }));
