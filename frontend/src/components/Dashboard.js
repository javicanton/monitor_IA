import React, { useState } from 'react';
import { 
  Container, 
  Box, 
  Typography, 
  Paper,
  Alert,
  Chip,
  Grid,
  Stack
} from '@mui/material';
import { 
  TrendingUp as TrendingIcon,
  Info as InfoIcon 
} from '@mui/icons-material';
import FilterBar from './FilterBar';
import MessageList from './MessageList';
import ScoreExplanation from './ScoreExplanation';

const Dashboard = () => {
  const [filters, setFilters] = useState({});
  const [channels, setChannels] = useState([]);
  const [stats, setStats] = useState({
    totalMessages: 0,
    relevantMessages: 0,
    averageScore: 0
  });

  const handleFilterChange = (newFilters) => {
    setFilters(newFilters);
  };

  const handleChannelsLoad = (loadedChannels) => {
    setChannels(loadedChannels);
  };

  const handleStatsUpdate = (newStats) => {
    setStats(newStats);
  };

  return (
    <Container maxWidth="xl" sx={{ py: 4 }}>
      {/* Header principal */}
      <Box textAlign="center" mb={6}>
        <Typography variant="h3" component="h1" gutterBottom color="primary">
          <TrendingIcon sx={{ mr: 2, verticalAlign: 'middle' }} />
          Mensajes de Alto Rendimiento en Telegram
        </Typography>
        
        <Typography variant="h6" color="textSecondary" paragraph>
          Analiza y etiqueta mensajes relevantes de canales de Telegram
        </Typography>

        {/* Estadísticas generales */}
        <Paper sx={{ p: 3, mt: 3, display: 'inline-block' }}>
          <Stack direction="row" spacing={3} alignItems="center">
            <Box textAlign="center">
              <Typography variant="h4" color="primary" fontWeight="bold">
                {stats.totalMessages}
              </Typography>
              <Typography variant="body2" color="textSecondary">
                Total Mensajes
              </Typography>
            </Box>
            
            <Box textAlign="center">
              <Typography variant="h4" color="success.main" fontWeight="bold">
                {stats.relevantMessages}
              </Typography>
              <Typography variant="body2" color="textSecondary">
                Relevantes
              </Typography>
            </Box>
            
            <Box textAlign="center">
              <Typography variant="h4" color="info.main" fontWeight="bold">
                {stats.averageScore.toFixed(2)}
              </Typography>
              <Typography variant="body2" color="textSecondary">
                Score Promedio
              </Typography>
            </Box>
          </Stack>
        </Paper>
      </Box>

      <Grid container spacing={4} alignItems="flex-start">
        <Grid item xs={12} md={8} order={{ xs: 2, md: 1 }}>
          {/* Explicación del sistema de puntuación */}
          <Box mb={4}>
            <ScoreExplanation />
          </Box>

          {/* Información sobre la conexión S3 */}
          <Alert 
            severity="info" 
            icon={<InfoIcon />}
            sx={{ mb: 4 }}
          >
            <Typography variant="body1" gutterBottom>
              <strong>Conectado a AWS S3:</strong> Los datos se cargan automáticamente desde el bucket 
              <Chip 
                label="monitoria-data" 
                size="small" 
                color="primary" 
                sx={{ mx: 1 }} 
              />
              y se sincronizan en tiempo real.
            </Typography>
            <Typography variant="body2">
              Los cambios en las etiquetas se guardan tanto localmente como en la nube para mayor seguridad.
            </Typography>
          </Alert>

          {/* Información de canales disponibles */}
          {channels.length > 0 && (
            <Paper sx={{ p: 2, mb: 3, bgcolor: 'grey.50' }}>
              <Typography variant="subtitle2" color="textSecondary" gutterBottom>
                Canales disponibles ({channels.length}):
              </Typography>
              <Box display="flex" flexWrap="wrap" gap={1}>
                {channels.slice(0, 10).map((channel) => (
                  <Chip 
                    key={channel} 
                    label={channel} 
                    size="small" 
                    variant="outlined"
                    onClick={() => setFilters(prev => ({ ...prev, channel }))}
                    sx={{ cursor: 'pointer' }}
                  />
                ))}
                {channels.length > 10 && (
                  <Chip 
                    label={`+${channels.length - 10} más`} 
                    size="small" 
                    variant="outlined"
                    color="primary"
                  />
                )}
              </Box>
            </Paper>
          )}

          {/* Lista de mensajes */}
          <MessageList 
            filters={filters}
            onStatsUpdate={handleStatsUpdate}
          />
        </Grid>

        <Grid item xs={12} md={4} order={{ xs: 1, md: 2 }}>
          {/* Barra de filtros */}
          <FilterBar 
            onFilterChange={handleFilterChange}
            onChannelsLoad={handleChannelsLoad}
          />
        </Grid>
      </Grid>

      {/* Footer informativo */}
      <Box mt={6} textAlign="center">
        <Typography variant="body2" color="textSecondary">
          Los datos se actualizan automáticamente desde AWS S3. 
          Las etiquetas se sincronizan en tiempo real entre todos los usuarios.
        </Typography>
      </Box>
    </Container>
  );
};

export default Dashboard;
