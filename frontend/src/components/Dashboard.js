import React, { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { 
  Container, 
  Box, 
  Paper,
  Grid,
  TextField,
  Button,
  InputAdornment,
  Typography,
  CircularProgress,
} from '@mui/material';
import { Search as SearchIcon } from '@mui/icons-material';
import FilterBar from './FilterBar';
import MessageList from './MessageList';
import ScoreExplanation from './ScoreExplanation';
import MessagesOverTimeChart from './MessagesOverTimeChart';
import ChartErrorBoundary from './ChartErrorBoundary';
import logo from '../assets/Logo_MonitorIA ajustado.png';

const SCROLL_THRESHOLD = 180;
const LOGO_SIZE = { xs: 210, sm: 270, md: 330 };
const LOGO_SIZE_SMALL = 88;

const Dashboard = () => {
  const [filters, setFilters] = useState({});
  const [searchInput, setSearchInput] = useState('');
  const [searchPending, setSearchPending] = useState(false);
  const [scrollProgress, setScrollProgress] = useState(0);
  const logoRef = useRef(null);
  const [logoTransform, setLogoTransform] = useState({
    shiftX: 0,
    shiftY: 0,
    scaleTarget: 1
  });

  useEffect(() => {
    const handleScroll = () => {
      const progress = Math.min(window.scrollY / SCROLL_THRESHOLD, 1);
      setScrollProgress(progress);
    };
    handleScroll();
    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  useLayoutEffect(() => {
    const updateLogoTransform = () => {
      if (!logoRef.current) {
        return;
      }
      const rect = logoRef.current.getBoundingClientRect();
      const targetX = 16;
      const targetY = 16;
      const scaleTarget = rect.width ? LOGO_SIZE_SMALL / rect.width : 1;

      setLogoTransform({
        shiftX: targetX - rect.left,
        shiftY: targetY - rect.top,
        scaleTarget: Math.min(scaleTarget, 1)
      });
    };

    updateLogoTransform();
    window.addEventListener('resize', updateLogoTransform);
    return () => window.removeEventListener('resize', updateLogoTransform);
  }, []);

  const handleFilterChange = (newFilters) => {
    setFilters(newFilters);
    setSearchInput(newFilters.search ?? '');
    setSearchPending(false);
  };

  const handleSearchApply = () => {
    setSearchPending(true);
    setFilters((prev) => ({ ...prev, search: searchInput.trim() }));
  };

  const handleDateRangeFromChart = (dateStart, dateEnd) => {
    setFilters((prev) => ({ ...prev, dateStart, dateEnd }));
  };

  const handleChannelsLoad = () => {};

  const clampedProgress = Math.min(scrollProgress, 1);
  const largeLogoOpacity = 1 - clampedProgress;
  const largeLogoScale = 1 - clampedProgress * (1 - logoTransform.scaleTarget);
  const largeLogoTranslateX = logoTransform.shiftX * clampedProgress;
  const largeLogoTranslateY = logoTransform.shiftY * clampedProgress;
  const floatingLogoOpacity = clampedProgress;
  const floatingLogoScale = 1.25 - clampedProgress * 0.25;

  return (
    <Container maxWidth="xl" sx={{ py: 4, overflow: 'visible' }}>
      <Box
        sx={{
          position: 'fixed',
          top: 16,
          left: 16,
          zIndex: 1200,
          width: { xs: 64, sm: 72, md: LOGO_SIZE_SMALL },
          height: 'auto',
          pointerEvents: 'none',
          bgcolor: 'transparent',
          opacity: floatingLogoOpacity,
          transform: `scale(${floatingLogoScale})`,
          transformOrigin: 'top left',
          transition: 'transform 0.2s ease, opacity 0.2s ease'
        }}
      >
        <Box
          component="img"
          src={logo}
          alt="MonitorIA"
          sx={{ width: '100%', height: 'auto' }}
        />
      </Box>

      {/* Header principal con logo centrado */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          mb: 2
        }}
      >
        <Box
          component="img"
          src={logo}
          alt="MonitorIA"
          ref={logoRef}
          sx={{
            width: { xs: LOGO_SIZE.xs, sm: LOGO_SIZE.sm, md: LOGO_SIZE.md },
            height: 'auto',
            flexShrink: 0,
            opacity: largeLogoOpacity,
            transform: `translate(${largeLogoTranslateX}px, ${largeLogoTranslateY}px) scale(${largeLogoScale})`,
            transition: 'transform 0.2s ease, opacity 0.2s ease'
          }}
        />
      </Box>

      {/* Nota explicativa - debajo del header, arriba del filtro */}
      <Box mb={2}>
        <ScoreExplanation />
      </Box>

      <Grid container spacing={4} alignItems="flex-start">
        <Grid
          item
          xs={12}
          order={{ xs: 2, md: 1 }}
          sx={{ flexBasis: { md: '80%' }, maxWidth: { md: '80%' } }}
        >

          {/* Gráfico de evolución de mensajes (filtro de fechas por rango) */}
          <ChartErrorBoundary>
            <MessagesOverTimeChart
              filters={filters}
              onDateRangeChange={handleDateRangeFromChart}
              selectedDateStart={filters.dateStart}
              selectedDateEnd={filters.dateEnd}
            />
          </ChartErrorBoundary>

          {/* Barra de búsqueda en mensajes */}
          <Paper sx={{ p: 2, mb: 3 }} elevation={0} variant="outlined">
            <Box display="flex" gap={2} alignItems="center" flexWrap="wrap">
              <TextField
                fullWidth
                size="small"
                label="Buscar en mensajes"
                placeholder="Palabras en el texto del mensaje o en el enlace"
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSearchApply()}
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <SearchIcon color="action" />
                    </InputAdornment>
                  )
                }}
                sx={{ flex: { xs: '1 1 100%', sm: '1 1 auto' }, minWidth: 200 }}
              />
              <Button
                variant="contained"
                onClick={handleSearchApply}
                startIcon={searchPending ? <CircularProgress size={16} color="inherit" /> : <SearchIcon />}
                disabled={searchPending}
                sx={{ flexShrink: 0 }}
              >
                {searchPending ? 'Buscando…' : 'Buscar'}
              </Button>
            </Box>
            <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1 }}>
              La búsqueda se realiza sobre el texto almacenado del mensaje y su enlace (URL).
              No incluye el nombre del canal ni el widget de Telegram visible en la tarjeta.
            </Typography>
            {filters.search && (
              <Typography variant="caption" color="primary" display="block" sx={{ mt: 0.5 }}>
                Búsqueda activa: «{filters.search}»
              </Typography>
            )}
          </Paper>

          {/* Lista de mensajes */}
          <MessageList 
            filters={filters}
            onLoadingChange={setSearchPending}
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
            currentFilters={filters}
          />
        </Grid>
      </Grid>

    </Container>
  );
};

export default Dashboard;
