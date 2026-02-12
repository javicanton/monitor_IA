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

const SCROLL_THRESHOLD = 180;
const LOGO_SIZE = { xs: 180, sm: 220, md: 260 };
const LOGO_SIZE_SMALL = 88;

const Dashboard = () => {
  const [filters, setFilters] = useState({});
  const [channels, setChannels] = useState([]);
  const [scrollProgress, setScrollProgress] = useState(0);

  useEffect(() => {
    const handleScroll = () => {
      const progress = Math.min(window.scrollY / SCROLL_THRESHOLD, 1);
      setScrollProgress(progress);
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

  const titleOpacity = 1 - scrollProgress;

  return (
    <Container maxWidth="xl" sx={{ py: 4, overflow: 'visible' }}>
      {/* Header sticky con transición */}
      <Box
        sx={{
          position: 'sticky',
          top: 0,
          zIndex: 1100,
          bgcolor: 'background.paper',
          transition: 'box-shadow 0.2s ease',
          boxShadow: scrollProgress > 0 ? 2 : 0,
          mb: 4,
          px: 2
        }}
      >
        <Box
          sx={{
            display: 'flex',
            flexDirection: { xs: 'column', md: 'row' },
            alignItems: 'center',
            justifyContent: { xs: 'center', md: 'flex-start' },
            gap: { xs: 2, md: 3 },
            py: scrollProgress > 0 ? 1.5 : 0,
            transition: 'padding 0.2s ease',
            minHeight: scrollProgress > 0 ? LOGO_SIZE_SMALL : undefined
          }}
        >
          <Box
            component="img"
            src={logo}
            alt="MonitorIA"
            sx={{
              width: {
                xs: scrollProgress > 0 ? LOGO_SIZE_SMALL : LOGO_SIZE.xs,
                sm: scrollProgress > 0 ? LOGO_SIZE_SMALL : LOGO_SIZE.sm,
                md: scrollProgress > 0 ? LOGO_SIZE_SMALL : LOGO_SIZE.md
              },
              height: 'auto',
              flexShrink: 0,
              transition: 'width 0.25s ease-out',
              alignSelf: scrollProgress > 0 ? 'flex-start' : 'center'
            }}
          />
          <Box
            sx={{
              ml: { xs: 0, md: 5 },
              textAlign: { xs: 'center', md: 'left' },
              opacity: titleOpacity,
              transition: 'opacity 0.2s ease',
              visibility: titleOpacity > 0.01 ? 'visible' : 'hidden'
            }}
          >
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
      </Box>

      {/* Nota explicativa - debajo del header, arriba del filtro */}
      <Box mb={3}>
        <ScoreExplanation />
      </Box>

      <Grid container spacing={4} alignItems="flex-start">
        <Grid
          item
          xs={12}
          order={{ xs: 2, md: 1 }}
          sx={{ flexBasis: { md: '80%' }, maxWidth: { md: '80%' } }}
        >

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
