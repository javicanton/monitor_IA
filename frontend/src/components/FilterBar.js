import React, { useState, useEffect } from 'react';
import Paper from '@mui/material/Paper';
import Grid from '@mui/material/Grid';
import TextField from '@mui/material/TextField';
import MenuItem from '@mui/material/MenuItem';
import Button from '@mui/material/Button';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Autocomplete from '@mui/material/Autocomplete';
import { FilterList as FilterIcon, Clear as ClearIcon } from '@mui/icons-material';
import DatePicker from 'react-datepicker';
import { es } from 'date-fns/locale';
import 'react-datepicker/dist/react-datepicker.css';
import { channelsAPI, topicsAPI } from '../utils/api';
import config from '../config';

const MEDIA_TYPE_OPTIONS = [
  { value: '__all__', label: 'Todos los tipos' },
  ...config.MEDIA_TYPES
];

const DateRangeInput = React.forwardRef(function DateRangeInput(
  { value, onClick },
  ref
) {
  return (
    <TextField
      fullWidth
      size="small"
      placeholder="Seleccionar rango de fechas"
      value={value || ''}
      onClick={onClick}
      onChange={() => {}}
      inputRef={ref}
      InputProps={{ readOnly: true }}
    />
  );
});

function toYYYYMMDD(date) {
  if (!date) return '';
  const d = new Date(date);
  return d.toISOString().slice(0, 10);
}

function fromYYYYMMDD(str) {
  if (!str) return null;
  const d = new Date(str + 'T12:00:00');
  return isNaN(d.getTime()) ? null : d;
}

function FilterBar({ onFilterChange, onChannelsLoad }) {
  const [channels, setChannels] = useState([]);
  const [loading, setLoading] = useState(false);
  const [topics, setTopics] = useState([]);
  const [loadingTopics, setLoadingTopics] = useState(false);
  const [filters, setFilters] = useState({
    dateStart: '',
    dateEnd: '',
    channel: [],
    topics: [],
    scoreMin: '',
    scoreMax: '',
    mediaType: [],
    sortBy: 'score'
  });
  const [hasPendingChanges, setHasPendingChanges] = useState(false);
  const [appliedFilters, setAppliedFilters] = useState({
    dateStart: '',
    dateEnd: '',
    channel: [],
    topics: [],
    scoreMin: '',
    scoreMax: '',
    mediaType: [],
    sortBy: 'score'
  });

  useEffect(() => {
    // Cargar canales al montar el componente
    fetchChannels();
    fetchTopics();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const fetchChannels = async () => {
    try {
      setLoading(true);
      const uniqueChannels = await channelsAPI.getChannels();
      setChannels(uniqueChannels);
      if (onChannelsLoad) {
        onChannelsLoad(uniqueChannels);
      }
    } catch (error) {
      console.error('Error al cargar canales:', error);
      // Si falla, usar canales por defecto
      setChannels(['Canal 1', 'Canal 2', 'Canal 3']);
    } finally {
      setLoading(false);
    }
  };

  const fetchTopics = async () => {
    try {
      setLoadingTopics(true);
      const availableTopics = await topicsAPI.getTopics();
      setTopics(availableTopics);
    } catch (error) {
      console.error('Error al cargar topics:', error);
      setTopics([]);
    } finally {
      setLoadingTopics(false);
    }
  };

  const handleFilterChange = (field) => (event) => {
    const newFilters = {
      ...filters,
      [field]: event.target.value
    };
    setFilters(newFilters);
    setHasPendingChanges(JSON.stringify(newFilters) !== JSON.stringify(appliedFilters));
  };

  const handleDateRangeChange = (dates) => {
    const [start, end] = dates;
    const newFilters = {
      ...filters,
      dateStart: toYYYYMMDD(start),
      dateEnd: toYYYYMMDD(end)
    };
    setFilters(newFilters);
    setHasPendingChanges(JSON.stringify(newFilters) !== JSON.stringify(appliedFilters));
  };

  const dateRangeValue = [
    fromYYYYMMDD(filters.dateStart),
    fromYYYYMMDD(filters.dateEnd)
  ];

  const handleApplyFilters = () => {
    // Validar fechas
    if (filters.dateStart && filters.dateEnd && filters.dateStart > filters.dateEnd) {
      alert('La fecha de inicio no puede ser posterior a la fecha de fin');
      return;
    }

    // Validar puntuaciones
    if (filters.scoreMin && filters.scoreMax && parseFloat(filters.scoreMin) > parseFloat(filters.scoreMax)) {
      alert('La puntuación mínima no puede ser mayor que la máxima');
      return;
    }

    onFilterChange(filters);
    setAppliedFilters(filters);
    setHasPendingChanges(false);
  };

  const handleReset = () => {
    const resetFilters = {
      dateStart: '',
      dateEnd: '',
      channel: [],
      topics: [],
      scoreMin: '',
      scoreMax: '',
      mediaType: [],
      sortBy: 'score'
    };
    setFilters(resetFilters);
    onFilterChange(resetFilters);
    setAppliedFilters(resetFilters);
    setHasPendingChanges(false);
  };

  const handleRefreshChannels = () => {
    fetchChannels();
  };

  const handleRefreshTopics = () => {
    fetchTopics();
  };

  const selectedTopics = topics.filter((topic) => filters.topics.includes(topic.id));
  const selectedTopicLabels =
    selectedTopics.length > 0
      ? selectedTopics.map((item) => item.label || item.id)
      : filters.topics.map((item) => item);

  return (
    <Paper
      sx={{
        p: 2,
        mb: 3,
        maxHeight: { md: 'calc(100vh - 48px)' },
        overflowY: { md: 'auto' }
      }}
    >
      <Box display="flex" alignItems="center" mb={2}>
        <FilterIcon sx={{ mr: 1 }} />
        <Typography variant="h6" component="h2">
          Filtros de Búsqueda
        </Typography>
      </Box>

      <Grid container spacing={2} alignItems="center">
        {/* Filtro de canal (múltiple con buscador) */}
        <Grid item xs={12}>
          <Autocomplete
            multiple
            options={channels}
            value={filters.channel}
            onChange={(_, value) => {
              const newFilters = { ...filters, channel: value };
              setFilters(newFilters);
              setHasPendingChanges(JSON.stringify(newFilters) !== JSON.stringify(appliedFilters));
            }}
            filterSelectedOptions
            disabled={loading}
            renderInput={(params) => (
              <TextField
                {...params}
                label="Canal"
                placeholder="Buscar canal..."
                size="small"
              />
            )}
          />
          <Box display="flex" gap={1} mt={1} flexWrap="wrap">
            <Button
              variant="outlined"
              size="small"
              onClick={() => {
                const newFilters = { ...filters, channel: channels };
                setFilters(newFilters);
                setHasPendingChanges(JSON.stringify(newFilters) !== JSON.stringify(appliedFilters));
              }}
              disabled={loading || channels.length === 0}
            >
              Seleccionar todos
            </Button>
            <Button
              variant="text"
              size="small"
              onClick={() => {
                const newFilters = { ...filters, channel: [] };
                setFilters(newFilters);
                setHasPendingChanges(JSON.stringify(newFilters) !== JSON.stringify(appliedFilters));
              }}
              disabled={loading || filters.channel.length === 0}
            >
              Limpiar canales
            </Button>
          </Box>
          <Typography variant="caption" color="textSecondary" display="block" mt={0.5}>
            {filters.channel.length === 0
              ? 'Ningún canal seleccionado'
              : `${filters.channel.length} canales seleccionados`}
          </Typography>
        </Grid>

        {/* Filtro de topics (múltiple con buscador) */}
        <Grid item xs={12}>
          <Autocomplete
            multiple
            options={topics}
            value={selectedTopics}
            onChange={(_, value) => {
              const newFilters = { ...filters, topics: value.map((item) => item.id) };
              setFilters(newFilters);
              setHasPendingChanges(JSON.stringify(newFilters) !== JSON.stringify(appliedFilters));
            }}
            getOptionLabel={(option) => option.label || `Topic ${option.id}`}
            isOptionEqualToValue={(option, value) => option.id === value.id}
            filterSelectedOptions
            disabled={loadingTopics}
            renderInput={(params) => (
              <TextField
                {...params}
                label="Temas"
                placeholder="Buscar tema..."
                size="small"
              />
            )}
          />
          <Typography variant="caption" color="textSecondary" display="block" mt={0.5}>
            {filters.topics.length === 0
              ? 'Ningún tema seleccionado'
              : `${filters.topics.length} temas seleccionados`}
          </Typography>
        </Grid>

        {/* Filtro de ordenamiento */}
        <Grid item xs={12}>
          <TextField
            fullWidth
            select
            label="Ordenar por"
            value={filters.sortBy}
            onChange={handleFilterChange('sortBy')}
            size="small"
          >
            <MenuItem value="score">Puntuación (Score)</MenuItem>
            <MenuItem value="views">Número de vistas</MenuItem>
            <MenuItem value="date">Fecha</MenuItem>
            <MenuItem value="channel">Canal</MenuItem>
          </TextField>
        </Grid>

        {/* Filtros de fecha - calendario unificado con rango */}
        <Grid item xs={12}>
          <Typography variant="subtitle2" color="textSecondary" gutterBottom>
            Fecha
          </Typography>
          <DatePicker
            selectsRange
            startDate={dateRangeValue[0]}
            endDate={dateRangeValue[1]}
            onChange={handleDateRangeChange}
            monthsShown={2}
            locale={es}
            dateFormat="d MMM yyyy"
            isClearable
            placeholderText="Seleccionar rango de fechas"
            customInput={<DateRangeInput />}
          />
        </Grid>

        {/* Filtro de tipo de contenido (selección múltiple) */}
        <Grid item xs={12}>
          <Autocomplete
            multiple
            options={MEDIA_TYPE_OPTIONS}
            value={
              filters.mediaType.length === 0
                ? [MEDIA_TYPE_OPTIONS[0]]
                : filters.mediaType.map((v) => MEDIA_TYPE_OPTIONS.find((o) => o.value === v)).filter(Boolean)
            }
            onChange={(_, newValue) => {
              const hasAll = newValue.some((o) => o.value === '__all__');
              const newMediaType =
                hasAll || newValue.length === 0
                  ? []
                  : newValue.filter((o) => o.value !== '__all__').map((o) => o.value);
              const newFilters = { ...filters, mediaType: newMediaType };
              setFilters(newFilters);
              setHasPendingChanges(JSON.stringify(newFilters) !== JSON.stringify(appliedFilters));
            }}
            getOptionLabel={(option) => option.label}
            isOptionEqualToValue={(option, value) => option.value === value.value}
            filterSelectedOptions
            renderInput={(params) => (
              <TextField
                {...params}
                label="Tipo de contenido"
                placeholder="Todos los tipos o elegir..."
                size="small"
              />
            )}
          />
        </Grid>

        {/* Filtros de puntuación */}
        <Grid item xs={12}>
          <Typography variant="subtitle2" color="textSecondary" gutterBottom>
            Puntuación
          </Typography>
          <Box display="flex" gap={1}>
            <TextField
              fullWidth
              type="number"
              label="Min"
              value={filters.scoreMin}
              onChange={handleFilterChange('scoreMin')}
              inputProps={{ 
                step: 0.1, 
                min: 0,
                placeholder: "0.0"
              }}
              size="small"
            />
            <TextField
              fullWidth
              type="number"
              label="Max"
              value={filters.scoreMax}
              onChange={handleFilterChange('scoreMax')}
              inputProps={{ 
                step: 0.1, 
                min: 0,
                placeholder: "10.0"
              }}
              size="small"
            />
          </Box>
        </Grid>

        {/* Botones de acción */}
        <Grid item xs={12}>
          <Box display="flex" gap={2} flexWrap="wrap">
            <Button
              variant="contained"
              color={hasPendingChanges ? 'warning' : 'primary'}
              onClick={handleApplyFilters}
              startIcon={<FilterIcon />}
              size="medium"
            >
              Aplicar Filtros
            </Button>
            
            <Button
              variant="outlined"
              color="secondary"
              onClick={handleReset}
              startIcon={<ClearIcon />}
              size="medium"
            >
              Limpiar Filtros
            </Button>
            
            <Button
              variant="outlined"
              onClick={handleRefreshChannels}
              disabled={loading}
              size="medium"
            >
              {loading ? 'Cargando...' : 'Actualizar Canales'}
            </Button>
            <Button
              variant="outlined"
              onClick={handleRefreshTopics}
              disabled={loadingTopics}
              size="medium"
            >
              {loadingTopics ? 'Cargando...' : 'Actualizar Temas'}
            </Button>
          </Box>
        </Grid>
      </Grid>

      {/* Información sobre filtros activos */}
          {(Object.values(filters).some(value => value !== '' && value !== 'score') || hasPendingChanges) && (
        <Box mt={2} p={2} bgcolor="grey.50" borderRadius={1}>
          <Typography variant="body2" color="textSecondary">
            <strong>Filtros activos:</strong>
            {filters.channel.length > 0 && ` Canales: ${filters.channel.join(', ')}`}
            {filters.topics.length > 0 && ` Temas: ${selectedTopicLabels.join(', ')}`}
            {filters.sortBy !== 'score' && ` Orden: ${filters.sortBy}`}
            {(filters.dateStart || filters.dateEnd) && ` Fecha: ${filters.dateStart || '...'} - ${filters.dateEnd || '...'}`}
            {filters.mediaType.length > 0 &&
              ` Tipo: ${filters.mediaType
                .map((v) => MEDIA_TYPE_OPTIONS.find((o) => o.value === v)?.label ?? v)
                .join(', ')}`}
            {(filters.scoreMin || filters.scoreMax) && ` Puntuación: ${filters.scoreMin || '...'} - ${filters.scoreMax || '...'}`}
          </Typography>
          {hasPendingChanges && (
            <Typography variant="body2" color="warning.main" sx={{ mt: 1 }}>
              Filtros pendientes de aplicar
            </Typography>
          )}
        </Box>
      )}
    </Paper>
  );
}

export default FilterBar;
