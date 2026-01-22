import React, { useState, useEffect } from 'react';
import Paper from '@mui/material/Paper';
import Grid from '@mui/material/Grid';
import TextField from '@mui/material/TextField';
import MenuItem from '@mui/material/MenuItem';
import Button from '@mui/material/Button';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import { FilterList as FilterIcon, Clear as ClearIcon } from '@mui/icons-material';
import { messagesAPI } from '../utils/api';

function FilterBar({ onFilterChange, onChannelsLoad }) {
  const [channels, setChannels] = useState([]);
  const [loading, setLoading] = useState(false);
  const [filters, setFilters] = useState({
    dateStart: '',
    dateEnd: '',
    channel: '',
    scoreMin: '',
    scoreMax: '',
    mediaType: '',
    sortBy: 'score'
  });
  const [hasPendingChanges, setHasPendingChanges] = useState(false);
  const [appliedFilters, setAppliedFilters] = useState({
    dateStart: '',
    dateEnd: '',
    channel: '',
    scoreMin: '',
    scoreMax: '',
    mediaType: '',
    sortBy: 'score'
  });

  useEffect(() => {
    // Cargar canales al montar el componente
    fetchChannels();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const fetchChannels = async () => {
    try {
      setLoading(true);
      // Usar una petición más pequeña para obtener canales
      const response = await messagesAPI.getMessages({ page: 1, per_page: 50 });
      
      if (response.success && response.messages) {
        // Extraer canales únicos de los mensajes
        const uniqueChannels = [...new Set(
          response.messages
            .map(msg => msg.Title)
            .filter(title => title && title !== 'Desconocido')
        )].sort();
        
        setChannels(uniqueChannels);
        
        // Notificar al componente padre sobre los canales cargados
        if (onChannelsLoad) {
          onChannelsLoad(uniqueChannels);
        }
      }
    } catch (error) {
      console.error('Error al cargar canales:', error);
      // Si falla, usar canales por defecto
      setChannels(['Canal 1', 'Canal 2', 'Canal 3']);
    } finally {
      setLoading(false);
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

    onFilterChange(filters);
    setAppliedFilters(filters);
    setHasPendingChanges(false);
  };

  const handleReset = () => {
    const resetFilters = {
      dateStart: '',
      dateEnd: '',
      channel: '',
      scoreMin: '',
      scoreMax: '',
      mediaType: '',
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

  return (
    <Paper sx={{ p: 3, mb: 3 }}>
      <Box display="flex" alignItems="center" mb={2}>
        <FilterIcon sx={{ mr: 1 }} />
        <Typography variant="h6" component="h2">
          Filtros de Búsqueda
        </Typography>
      </Box>

      <Grid container spacing={3} alignItems="center">
        {/* Filtros de fecha */}
        <Grid item xs={12} sm={6} md={3}>
          <TextField
            fullWidth
            type="date"
            label="Fecha desde"
            value={filters.dateStart}
            onChange={handleFilterChange('dateStart')}
            InputLabelProps={{ shrink: true }}
            size="small"
          />
        </Grid>
        
        <Grid item xs={12} sm={6} md={3}>
          <TextField
            fullWidth
            type="date"
            label="Fecha hasta"
            value={filters.dateEnd}
            onChange={handleFilterChange('dateEnd')}
            InputLabelProps={{ shrink: true }}
            size="small"
          />
        </Grid>

        {/* Filtro de canal */}
        <Grid item xs={12} sm={6} md={3}>
          <TextField
            fullWidth
            select
            label="Canal"
            value={filters.channel}
            onChange={handleFilterChange('channel')}
            size="small"
            disabled={loading}
          >
            <MenuItem value="">Todos los canales</MenuItem>
            {channels.map((channel) => (
              <MenuItem key={channel} value={channel}>
                {channel}
              </MenuItem>
            ))}
          </TextField>
        </Grid>

        {/* Filtros de puntuación */}
        <Grid item xs={12} sm={6} md={3}>
          <TextField
            fullWidth
            type="number"
            label="Puntuación mínima"
            value={filters.scoreMin}
            onChange={handleFilterChange('scoreMin')}
            inputProps={{ 
              step: 0.1, 
              min: 0,
              placeholder: "0.0"
            }}
            size="small"
          />
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <TextField
            fullWidth
            type="number"
            label="Puntuación máxima"
            value={filters.scoreMax}
            onChange={handleFilterChange('scoreMax')}
            inputProps={{ 
              step: 0.1, 
              min: 0,
              placeholder: "10.0"
            }}
            size="small"
          />
        </Grid>

        {/* Filtro de tipo de media */}
        <Grid item xs={12} sm={6} md={3}>
          <TextField
            fullWidth
            select
            label="Tipo de contenido"
            value={filters.mediaType}
            onChange={handleFilterChange('mediaType')}
            size="small"
          >
            <MenuItem value="">Todos los tipos</MenuItem>
            <MenuItem value="text">Texto</MenuItem>
            <MenuItem value="photo">Foto</MenuItem>
            <MenuItem value="video">Video</MenuItem>
            <MenuItem value="link">Enlace</MenuItem>
            <MenuItem value="document">Documento</MenuItem>
            <MenuItem value="audio">Audio</MenuItem>
            <MenuItem value="sticker">Sticker</MenuItem>
          </TextField>
        </Grid>

        {/* Filtro de ordenamiento */}
        <Grid item xs={12} sm={6} md={3}>
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

        {/* Botones de acción */}
        <Grid item xs={12}>
          <Box display="flex" gap={2} flexWrap="wrap">
            <Button
              variant="contained"
              color={hasPendingChanges ? 'warning' : 'primary'}
              onClick={handleApplyFilters}
              startIcon={<FilterIcon />}
              size="large"
            >
              Aplicar Filtros
            </Button>
            
            <Button
              variant="outlined"
              color="secondary"
              onClick={handleReset}
              startIcon={<ClearIcon />}
              size="large"
            >
              Limpiar Filtros
            </Button>
            
            <Button
              variant="outlined"
              onClick={handleRefreshChannels}
              disabled={loading}
              size="large"
            >
              {loading ? 'Cargando...' : 'Actualizar Canales'}
            </Button>
          </Box>
        </Grid>
      </Grid>

      {/* Información sobre filtros activos */}
      {(Object.values(filters).some(value => value !== '' && value !== 'score') || hasPendingChanges) && (
        <Box mt={2} p={2} bgcolor="grey.50" borderRadius={1}>
          <Typography variant="body2" color="textSecondary">
            <strong>Filtros activos:</strong>
            {filters.dateStart && ` Desde: ${filters.dateStart}`}
            {filters.dateEnd && ` Hasta: ${filters.dateEnd}`}
            {filters.channel && ` Canal: ${filters.channel}`}
            {filters.scoreMin && ` Score ≥ ${filters.scoreMin}`}
            {filters.scoreMax && ` Score ≤ ${filters.scoreMax}`}
            {filters.mediaType && ` Tipo: ${filters.mediaType}`}
            {filters.sortBy !== 'score' && ` Orden: ${filters.sortBy}`}
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
