-- Candidatos de snowball. No admite canales: solo lista.
-- Dirección de monitorIA: source = canal de origen del reenvío, target = canal que reenvía.
-- Criterio: lo reenvían 2 o más semillas, o suma 20 o más reenvíos (de cualquier canal ya scrapeado).
-- Ejecutar con search_path del estudio, o con -v schema=reco|reco_test.
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -v schema=reco -f aws/sql/10_snowball_candidatos.sql
\set ON_ERROR_STOP on
\if :{?schema}
\else
\set schema reco
\endif
SET search_path TO :"schema";

SELECT s.username,
       s.title,
       count(DISTINCT e.target_channel_id) FILTER (WHERE rc.origen = 'semilla') AS n_canales_que_lo_reenvian,
       coalesce(sum(e.forward_count), 0) AS n_reenvios
FROM channel_edges e
JOIN channels s ON s.id = e.source_channel_id
JOIN channels t ON t.id = e.target_channel_id
LEFT JOIN monitored_channels mc ON lower(mc.username) = lower(s.username)
LEFT JOIN reco_canales rc ON lower(rc.username) = lower(t.username)
WHERE mc.id IS NULL
GROUP BY s.username, s.title
HAVING count(DISTINCT e.target_channel_id) FILTER (WHERE rc.origen = 'semilla') >= 2
    OR coalesce(sum(e.forward_count), 0) >= 20
ORDER BY n_canales_que_lo_reenvian DESC, n_reenvios DESC;
