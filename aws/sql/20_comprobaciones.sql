-- Comprobaciones del corpus. Lee el esquema indicado, no public.
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -v schema=reco -f aws/sql/20_comprobaciones.sql
\set ON_ERROR_STOP on
\if :{?schema}
\else
\set schema reco
\endif
SET search_path TO :"schema";

SELECT 'mensajes' AS k, count(*)::text AS v FROM messages
UNION ALL SELECT 'canales_con_mensajes', count(DISTINCT channel_id)::text FROM messages
UNION ALL SELECT 'primer_mensaje', min(date_sent)::text FROM messages
UNION ALL SELECT 'ultimo_mensaje', max(date_sent)::text FROM messages
UNION ALL SELECT 'aristas', count(*)::text FROM channel_edges;

SELECT c.username, date_trunc('month', m.date_sent)::date AS mes, count(*) AS n
FROM messages m
JOIN channels c ON c.id = m.channel_id
WHERE m.date_sent >= '2024-09-01' AND m.date_sent < '2026-01-01'
GROUP BY 1, 2
ORDER BY 1, 2;

SELECT regla, incluido, count(*) FROM reco_flags GROUP BY 1, 2 ORDER BY 1;
