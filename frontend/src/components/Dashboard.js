import React, { useEffect, useState } from 'react';
import { 
  Container, 
  Box, 
  Typography, 
  Paper,
  Chip,
  Grid,
} from '@mui/material';
import { 
  TrendingUp as TrendingIcon
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
    <Container maxWidth="xl" sx={{ py: 4, overflow: 'visible' }}>
      {showFloatingLogo && (
        <Box
          sx={{
            position: 'fixed',
            top: 16,
            left: 16,
            zIndex: 1200,
            width: { xs: 72, sm: 88, md: 104 },
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
      <Box
        sx={{
          display: 'flex',
          flexDirection: { xs: 'column', md: 'row' },
          alignItems: 'center',
          justifyContent: { xs: 'center', md: 'flex-start' },
          gap: { xs: 2, md: 3 },
          mb: 4
        }}
      >
        <Box
          component="img"
          src={logo}
          alt="MonitorIA"
          sx={{
            width: { xs: 180, sm: 220, md: 260 },
            height: 'auto',
            flexShrink: 0
          }}
        />
        <Box sx={{ textAlign: { xs: 'center', md: 'left' } }}>
          <Typography
            variant="h3"
            component="h1"
            gutterBottom
            color="primary"
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: { xs: 'center', md: 'flex-start' }
            }}
          >
            <TrendingIcon sx={{ mr: 2, verticalAlign: 'middle' }} />
            Monitorización avanzada en Telegram
          </Typography>
        </Box>
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
          sx={{
            flexBasis: { md: '20%' },
            maxWidth: { md: '20%' },
            position: { md: 'sticky' },
            top: { md: 24 },
            alignSelf: { md: 'flex-start' },
            height: 'fit-content'
          }}
        >
          {/* Barra de filtros */}
          <FilterBar 
            onFilterChange={handleFilterChange}
            onChannelsLoad={handleChannelsLoad}
          />
        </Grid>
      </Grid>

    </Container>
  );
};

export default Dashboard;
