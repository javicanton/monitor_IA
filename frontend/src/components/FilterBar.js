import React, { useState, useEffect } from 'react';
import Paper from '@mui/material/Paper';
import Grid from '@mui/material/Grid';
import TextField from '@mui/material/TextField';
import MenuItem from '@mui/material/MenuItem';
import Button from '@mui/material/Button';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Autocomplete from '@mui/material/Autocomplete';
import Dialog from '@mui/material/Dialog';
import DialogTitle from '@mui/material/DialogTitle';
import DialogContent from '@mui/material/DialogContent';
import DialogActions from '@mui/material/DialogActions';
import Alert from '@mui/material/Alert';
import { FilterList as FilterIcon, Clear as ClearIcon, Add as AddIcon } from '@mui/icons-material';
import { channelsAPI, topicsAPI } from '../utils/api';
import config from '../config';

function FilterBar({ onFilterChange, onChannelsLoad, currentFilters = {} }) {
  const [channels, setChannels] = useState([]);
  const [loading, setLoading] = useState(false);
  const [topics, setTopics] = useState([]);
  const [loadingTopics, setLoadingTopics] = useState(false);
  const [filters, setFilters] = useState({
    search: '',
    dateStart: '',
    dateEnd: '',
    channel: [],
    excludeChannel: [],
    topics: [],
    scoreMin: '',
    scoreMax: '',
    mediaType: [],
    sortBy: 'score'
  });
  const [hasPendingChanges, setHasPendingChanges] = useState(false);
  const [appliedFilters, setAppliedFilters] = useState({
    search: '',
    dateStart: '',
    dateEnd: '',
    channel: [],
    excludeChannel: [],
    topics: [],
    scoreMin: '',
    scoreMax: '',
    mediaType: [],
    sortBy: 'score'
  });
  const [suggestOpen, setSuggestOpen] = useState(false);
  const [suggestForm, setSuggestForm] = useState({ username: '', note: '', email: '' });
  const [suggestLoading, setSuggestLoading] = useState(false);
  const [suggestFeedback, setSuggestFeedback] = useState({ type: '', message: '' });

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

    // Mantener la búsqueda que viene de la barra principal (fuera de este panel)
    const merged = {
      ...filters,
      search: currentFilters.search ?? '',
      dateStart: currentFilters.dateStart ?? '',
      dateEnd: currentFilters.dateEnd ?? ''
    };
    onFilterChange(merged);
    setAppliedFilters(merged);
    setHasPendingChanges(false);
  };

  const handleReset = () => {
    const resetFilters = {
      search: '',
      dateStart: '',
      dateEnd: '',
      channel: [],
      excludeChannel: [],
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

  const handleOpenSuggest = () => {
    setSuggestFeedback({ type: '', message: '' });
    setSuggestOpen(true);
  };

  const handleCloseSuggest = () => {
    if (!suggestLoading) {
      setSuggestOpen(false);
    }
  };

  const handleSuggestSubmit = async () => {
    const username = suggestForm.username.trim().replace(/^@/, '');
    if (!username) {
      setSuggestFeedback({ type: 'error', message: 'Indica el nombre de usuario del canal.' });
      return;
    }
    try {
      setSuggestLoading(true);
      setSuggestFeedback({ type: '', message: '' });
      const response = await channelsAPI.suggestChannel({
        username,
        note: suggestForm.note.trim(),
        email: suggestForm.email.trim(),
      });
      if (response.success) {
        setSuggestFeedback({
          type: 'success',
          message: response.message || 'Propuesta enviada correctamente.',
        });
        setSuggestForm({ username: '', note: '', email: '' });
      } else {
        throw new Error(response.error || 'No se pudo enviar la propuesta');
      }
    } catch (error) {
      setSuggestFeedback({
        type: 'error',
        message: error.response?.data?.error || error.message || 'Error al enviar la propuesta',
      });
    } finally {
      setSuggestLoading(false);
    }
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
          Filtros
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
          <Button
            variant="outlined"
            size="small"
            startIcon={<AddIcon />}
            onClick={handleOpenSuggest}
            sx={{ mt: 1 }}
          >
            Incluir canales
          </Button>
        </Grid>

        {/* Excluir canales (todos menos los seleccionados) */}
        <Grid item xs={12}>
          <Autocomplete
            multiple
            options={channels}
            value={filters.excludeChannel}
            onChange={(_, value) => {
              const newFilters = { ...filters, excludeChannel: value };
              setFilters(newFilters);
              setHasPendingChanges(JSON.stringify(newFilters) !== JSON.stringify(appliedFilters));
            }}
            filterSelectedOptions
            disabled={loading}
            renderInput={(params) => (
              <TextField
                {...params}
                label="Excluir canales"
                placeholder="Canales a omitir..."
                size="small"
              />
            )}
          />
          <Box display="flex" gap={1} mt={1} flexWrap="wrap">
            <Button
              variant="text"
              size="small"
              onClick={() => {
                const newFilters = { ...filters, excludeChannel: [] };
                setFilters(newFilters);
                setHasPendingChanges(JSON.stringify(newFilters) !== JSON.stringify(appliedFilters));
              }}
              disabled={loading || filters.excludeChannel.length === 0}
            >
              Limpiar exclusiones
            </Button>
          </Box>
          <Typography variant="caption" color="textSecondary" display="block" mt={0.5}>
            {filters.excludeChannel.length === 0
              ? 'Sin exclusiones (todos los canales)'
              : `${filters.excludeChannel.length} canales excluidos`}
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
            <MenuItem value="score">Overperforming Score</MenuItem>
            <MenuItem value="views">Nº visualizaciones</MenuItem>
            <MenuItem value="date">Fecha</MenuItem>
            <MenuItem value="channel">Canal</MenuItem>
          </TextField>
        </Grid>

        {/* Filtro de tipo de contenido (selección múltiple) */}
        <Grid item xs={12}>
          <Autocomplete
            multiple
            options={config.MEDIA_TYPES}
            value={config.MEDIA_TYPES.filter((item) => filters.mediaType.includes(item.value))}
            onChange={(_, newValue) => {
              const newFilters = {
                ...filters,
                mediaType: newValue.map((item) => item.value)
              };
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
                placeholder="Buscar tipo..."
                size="small"
              />
            )}
          />
          <Box display="flex" gap={1} mt={1} flexWrap="wrap">
            <Button
              variant="outlined"
              size="small"
              onClick={() => {
                const newFilters = { ...filters, mediaType: [] };
                setFilters(newFilters);
                setHasPendingChanges(JSON.stringify(newFilters) !== JSON.stringify(appliedFilters));
              }}
            >
              Todos los tipos
            </Button>
          </Box>
          <Typography variant="caption" color="textSecondary" display="block" mt={0.5}>
            {filters.mediaType.length === 0
              ? 'Todos los tipos'
              : `${filters.mediaType.length} tipos seleccionados`}
          </Typography>
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
          {(Object.values(filters).some(value => (Array.isArray(value) ? value.length > 0 : value !== '' && value !== 'score')) || (currentFilters.dateStart || currentFilters.dateEnd) || hasPendingChanges) && (
        <Box mt={2} p={2} bgcolor="grey.50" borderRadius={1}>
          <Typography variant="body2" color="textSecondary">
            <strong>Filtros activos:</strong>
            {currentFilters.search && ` Búsqueda: "${currentFilters.search}"`}
            {(currentFilters.dateStart || currentFilters.dateEnd) && ` Fecha: ${currentFilters.dateStart || '...'} - ${currentFilters.dateEnd || '...'}`}
            {filters.channel.length > 0 && ` Canales: ${filters.channel.join(', ')}`}
            {filters.excludeChannel.length > 0 && ` Excluidos: ${filters.excludeChannel.join(', ')}`}
            {filters.topics.length > 0 && ` Temas: ${selectedTopicLabels.join(', ')}`}
            {filters.sortBy !== 'score' && ` Orden: ${filters.sortBy}`}
            {filters.mediaType.length > 0 &&
              ` Tipo: ${filters.mediaType
                .map((v) => config.MEDIA_TYPES.find((o) => o.value === v)?.label ?? v)
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

      <Dialog open={suggestOpen} onClose={handleCloseSuggest} maxWidth="sm" fullWidth>
        <DialogTitle>Proponer canal para monitorizar</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="textSecondary" sx={{ mb: 2 }}>
            Indica el canal que quieres incluir. Enviaremos la propuesta al equipo de monitorización.
          </Typography>
          {suggestFeedback.message && (
            <Alert severity={suggestFeedback.type === 'success' ? 'success' : 'error'} sx={{ mb: 2 }}>
              {suggestFeedback.message}
            </Alert>
          )}
          <TextField
            autoFocus
            margin="dense"
            label="Usuario del canal"
            placeholder="ejemplo: canal_sin_arroba"
            fullWidth
            size="small"
            value={suggestForm.username}
            onChange={(e) => setSuggestForm({ ...suggestForm, username: e.target.value })}
            disabled={suggestLoading}
            sx={{ mb: 2 }}
          />
          <TextField
            margin="dense"
            label="Comentario (opcional)"
            placeholder="Motivo o contexto de la propuesta"
            fullWidth
            multiline
            minRows={2}
            size="small"
            value={suggestForm.note}
            onChange={(e) => setSuggestForm({ ...suggestForm, note: e.target.value })}
            disabled={suggestLoading}
            sx={{ mb: 2 }}
          />
          <TextField
            margin="dense"
            label="Tu email (opcional)"
            type="email"
            fullWidth
            size="small"
            value={suggestForm.email}
            onChange={(e) => setSuggestForm({ ...suggestForm, email: e.target.value })}
            disabled={suggestLoading}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseSuggest} disabled={suggestLoading}>
            Cancelar
          </Button>
          <Button variant="contained" onClick={handleSuggestSubmit} disabled={suggestLoading}>
            {suggestLoading ? 'Enviando...' : 'Enviar'}
          </Button>
        </DialogActions>
      </Dialog>
    </Paper>
  );
}

export default FilterBar;
