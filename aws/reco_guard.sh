# Funciones de aislamiento. Se cargan con source desde los lanzadores.
# No escriben en la base. Abortan si search_path no es el esquema del estudio
# o si el conteo de public.messages no es numérico.

reco_exigir_search_path() {
  local esperado="${RECO_SCHEMA:-reco}"
  local sp
  if ! sp="$(psql "$DATABASE_URL" -t -A -c 'SHOW search_path')"; then
    echo "ABORTO: no se pudo leer search_path"
    return 9
  fi
  sp="$(printf '%s' "$sp" | tr -d '[:space:]' | tr -d '"')"
  if [ "$sp" != "$esperado" ]; then
    echo "ABORTO: search_path=${sp:-vacio} (debe ser ${esperado})"
    return 9
  fi
  echo "search_path=${sp}"
}

reco_contar_public() {
  local url="${DATABASE_URL_ADMIN:-$DATABASE_URL}"
  local n
  if ! n="$(psql "$url" -t -A -c 'SELECT count(*) FROM public.messages')"; then
    echo "ABORTO: no se pudo contar public.messages" >&2
    return 9
  fi
  n="$(printf '%s' "$n" | tr -d '[:space:]')"
  case "$n" in
    ''|*[!0-9]*)
      echo "ABORTO: conteo de public.messages no numérico (${n})" >&2
      return 9
      ;;
  esac
  printf '%s\n' "$n"
}

reco_exigir_public_igual() {
  local antes="$1"
  local despues="$2"
  if [ "$antes" != "$despues" ]; then
    echo "ALERTA: public.messages cambió (${antes} -> ${despues})"
    return 10
  fi
  echo "public.messages sin cambios (${despues})"
}
