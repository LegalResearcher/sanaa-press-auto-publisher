-- Run the Sanaa Press publisher from Supabase pg_cron every 20 minutes.
-- The GitHub workflow remains workflow_dispatch-only; pg_net dispatches it
-- using the existing Vault secret without exposing the token in SQL logs.
DO $migration$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM cron.job
    WHERE jobname = 'sanaa-press-auto-publisher-every-20-min'
  ) THEN
    PERFORM cron.unschedule('sanaa-press-auto-publisher-every-20-min');
  END IF;

  PERFORM cron.schedule(
    'sanaa-press-auto-publisher-every-20-min',
    '*/20 * * * *',
    $job$
      SELECT net.http_post(
        url := 'https://api.github.com/repos/LegalResearcher/sanaa-press-auto-publisher/actions/workflows/auto_publish_shmsan.yml/dispatches',
        headers := jsonb_build_object(
          'Accept', 'application/vnd.github+json',
          'Authorization', 'Bearer ' || (
            SELECT decrypted_secret
            FROM vault.decrypted_secrets
            WHERE name = 'github_actions_token'
            LIMIT 1
          ),
          'Content-Type', 'application/json',
          'X-GitHub-Api-Version', '2022-11-28'
        ),
        body := jsonb_build_object('ref', 'main'),
        timeout_milliseconds := 10000
      );
    $job$
  );
END;
$migration$;
