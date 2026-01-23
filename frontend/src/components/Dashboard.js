import React, { useEffect, useState } from 'react';
import { 
  Container, 
  Box, 
  Typography, 
  Paper,
  Alert,
  Chip,
  Grid,
} from '@mui/material';
import { 
  TrendingUp as TrendingIcon,
  Info as InfoIcon 
} from '@mui/icons-material';
import FilterBar from './FilterBar';
import MessageList from './MessageList';
import ScoreExplanation from './ScoreExplanation';
import logo from '../assets/Logo_MonitorIA.png';

const Dashboard = () => {
  const [filters, setFilters] = useState({});
  const [channels, setChannels] = useState([]);
  const [showFloatingLogo, setShowFloatingLogo] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setShowFloatingLogo(window.scrollY > 80);
    };
    handleScroll();
    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const handleFilterChange = (newFilters) => {
    setFilters(newFilters);
  };

  const handleChannelsLoad = (loadedChannels) => {
    setChannels(loadedChannels);
  };

  return (
    <Container maxWidth="xl" sx={{ py: 4 }}>
      {showFloatingLogo && (
        <Box
          sx={{
            position: 'fixed',
            top: 16,
            right: 16,
            zIndex: 1200,
            width: { xs: 44, sm: 56 },
            height: 'auto',
            opacity: 0.9,
            pointerEvents: 'none'
          }}
        >
          <Box
            component="img"
            src={logo}
            alt="MonitorIA"
            sx={{ width: '100%', height: 'auto' }}
          />
        </Box>
      )}

      {/* Header principal */}
      <Box textAlign="center" mb={6}>
        <Box
          component="img"
          src={logo}
          alt="MonitorIA"
          sx={{
            width: { xs: 220, sm: 280, md: 360 },
            height: 'auto',
            mb: 2
          }}
        />
        <Typography variant="h3" component="h1" gutterBottom color="primary">
          <TrendingIcon sx={{ mr: 2, verticalAlign: 'middle' }} />
          Monitorización avanzada en Telegram
        </Typography>

      </Box>

      <Grid container spacing={4} alignItems="flex-start">
        <Grid
          item
          xs={12}
          order={{ xs: 2, md: 1 }}
          sx={{ flexBasis: { md: '80%' }, maxWidth: { md: '80%' } }}
        >
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
          />
        </Grid>

        <Grid
          item
          xs={12}
          order={{ xs: 1, md: 2 }}
          sx={{ flexBasis: { md: '20%' }, maxWidth: { md: '20%' } }}
        >
          {/* Barra de filtros */}
          <Box sx={{ position: { md: 'sticky' }, top: { md: 24 } }}>
            <FilterBar 
              onFilterChange={handleFilterChange}
              onChannelsLoad={handleChannelsLoad}
            />
          </Box>
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
