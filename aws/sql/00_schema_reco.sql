-- Esquema aislado del corpus RECO, en la misma base que monitorIA.
-- No crea nada en public: todas las tablas van calificadas con el esquema.
-- Uso:
--   psql "$DATABASE_URL_ADMIN" -v ON_ERROR_STOP=1 -v schema=reco_test -f aws/sql/00_schema_reco.sql
--   psql "$DATABASE_URL_ADMIN" -v ON_ERROR_STOP=1 -v schema=reco -f aws/sql/00_schema_reco.sql
-- Si no se pasa -v schema, el destino es reco (nunca public).
\set ON_ERROR_STOP on
\if :{?schema}
\else
\set schema reco
\endif

CREATE SCHEMA IF NOT EXISTS :"schema";
SET search_path TO :"schema";

-- Metadatos del estudio (tipo T1..T6, país, procedencia). No es una tabla de monitorIA.
CREATE TABLE IF NOT EXISTS :"schema".reco_canales (
    username        text PRIMARY KEY,
    nombre_documentado text,
    tipo            text,
    pais            text,
    origen          text,
    fuente_documental text,
    ronda_snowball  smallint DEFAULT 0,
    suscriptores    integer,
    vigente         boolean,
    admitido        boolean,
    fecha_captura   date,
    notas           text
);

-- Marcas del filtro léxico. No altera messages.
CREATE TABLE IF NOT EXISTS :"schema".reco_flags (
    message_pk      integer PRIMARY KEY,
    regla           text NOT NULL,
    incluido        smallint NOT NULL,
    hits_a          text,
    hits_b          text,
    hits_veto       text,
    lexico_version  text NOT NULL,
    flagged_at      timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_reco_flags_regla ON :"schema".reco_flags (regla);
