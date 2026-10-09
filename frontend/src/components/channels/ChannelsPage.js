import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Alert,
  Box,
  Button,
  Container,
  FormControlLabel,
  Paper,
  Stack,
  Switch,
  TextField,
  Typography,
  CircularProgress,
  Slider,
  useMediaQuery,
  Drawer,
  IconButton,
} from '@mui/material';
import { useTheme } from '@mui/material/styles';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import DownloadIcon from '@mui/icons-material/Download';
import CloseIcon from '@mui/icons-material/Close';
import { useAuth } from '../../auth/AuthContext';
import UserMenu from '../../auth/components/UserMenu';
import { channelsAPI } from '../../utils/api';
import ChannelGraph from './ChannelGraph';
import ChannelDetailPanel from './ChannelDetailPanel';
import logo from '../../assets/Logo_MonitorIA ajustado.png';

const ChannelsPage = () => {
  const { logout } = useAuth();
  const navigate = useNavigate();
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));

  const [graph, setGraph] = useState({ nodes: [], edges: [], meta: null });
  const [loadingGraph, setLoadingGraph] = useState(true);
  const [graphError, setGraphError] = useState('');
  const [search, setSearch] = useState('');
  const [minForwards, setMinForwards] = useState(1);
  const [onlyMonitored, setOnlyMonitored] = useState(false);
  const [includeDiscontinued, setIncludeDiscontinued] = useState(true);

  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [days, setDays] = useState(30);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [downloading, setDownloading] = useState(false);

  const handleLogout = async () => {
    await logout();
    navigate('/login', { replace: true });
  };

  const loadGraph = useCallback(async () => {
    try {
      setLoadingGraph(true);
      setGraphError('');
      const data = await channelsAPI.getGraph({
        min_forwards: minForwards,
        include_discontinued: includeDiscontinued,
      });
      setGraph({
        nodes: data.nodes || [],
        edges: data.edges || [],
        meta: data.meta || null,
      });
    } catch (err) {
      setGraphError(err.response?.data?.error || err.message || 'Error al cargar el grafo');
      setGraph({ nodes: [], edges: [], meta: null });
    } finally {
      setLoadingGraph(false);
    }
  }, [minForwards, includeDiscontinued]);

  useEffect(() => {
    loadGraph();
  }, [loadGraph]);

  const visibleGraph = useMemo(() => {
    let nodes = graph.nodes;
    if (onlyMonitored) {
      nodes = nodes.filter((n) => n.monitored);
    }
    const ids = new Set(nodes.map((n) => n.id));
    const edges = graph.edges.filter((e) => ids.has(e.source) && ids.has(e.target));
    return { nodes, edges };
  }, [graph, onlyMonitored]);

  const loadDetail = useCallback(async (username, daysWindow) => {
    if (!username) {
      setDetail(null);
      return;
    }
    try {
      setLoadingDetail(true);
      const data = await channelsAPI.getChannelStats(username, { days: daysWindow });
      setDetail(data);
    } catch (err) {
      console.error(err);
      setDetail(null);
    } finally {
      setLoadingDetail(false);
    }
  }, []);

  useEffect(() => {
    if (selectedId) {
      loadDetail(selectedId, days);
    } else {
      setDetail(null);
    }
  }, [selectedId, days, loadDetail]);

  const handleSelectNode = (node) => {
    const id = node?.id || node?.username || null;
    setSelectedId(id);
    if (isMobile && id) setDrawerOpen(true);
  };

  const handleSelectNeighbor = (username) => {
    setSelectedId(username);
    if (isMobile) setDrawerOpen(true);
  };

  const handleViewMessages = (channel) => {
    const title = channel?.title || channel?.username;
    if (!title) return;
    navigate(`/?channel=${encodeURIComponent(title)}`);
  };

  const handleDownload = async () => {
    try {
      setDownloading(true);
      const response = await channelsAPI.downloadChannelGraph();
      const blob = new Blob([response.data], { type: 'application/zip' });
      let filename = 'channel_graph.zip';
      const disposition = response.headers?.['content-disposition'];
      if (disposition) {
        const match = /filename="?([^"]+)"?/i.exec(disposition);
        if (match) filename = match[1];
      }
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error(err);
    } finally {
      setDownloading(false);
    }
  };

  const panel = (
    <ChannelDetailPanel
      meta={graph.meta}
      selectedUsername={selectedId}
      detail={detail}
      loading={loadingDetail}
      days={days}
      onDaysChange={setDays}
      onSelectNeighbor={handleSelectNeighbor}
      onViewMessages={handleViewMessages}
    />
  );

  return (
    <Container maxWidth="xl" sx={{ py: 3 }}>
      <UserMenu onLogout={handleLogout} />

      <Stack direction="row" alignItems="center" spacing={2} mb={2} flexWrap="wrap">
        <Box
          component="img"
          src={logo}
          alt="MonitorIA"
          sx={{ width: 56, height: 'auto', cursor: 'pointer' }}
          onClick={() => navigate('/')}
        />
        <Box flex={1} minWidth={180}>
          <Typography variant="h5" sx={{ fontWeight: 600 }}>Canales</Typography>
          <Typography variant="body2" color="text.secondary">
            Grafo de reenvíos y estadísticas por canal
          </Typography>
        </Box>
        <Button
          startIcon={<ArrowBackIcon />}
          onClick={() => navigate('/')}
          size="small"
        >
          Mensajes
        </Button>
        <Button
          startIcon={downloading ? <CircularProgress size={14} /> : <DownloadIcon />}
          onClick={handleDownload}
          disabled={downloading}
          size="small"
          variant="outlined"
        >
          Descargar CSV
        </Button>
      </Stack>

      <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
        <Stack
          direction={{ xs: 'column', md: 'row' }}
          spacing={2}
          alignItems={{ md: 'center' }}
        >
          <TextField
            size="small"
            label="Buscar canal"
            placeholder="@username o título"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            sx={{ minWidth: { md: 220 }, flex: 1 }}
          />
          <Box sx={{ width: { xs: '100%', md: 200 }, px: 1 }}>
            <Typography variant="caption" color="text.secondary">
              Mín. reenvíos: {minForwards}
            </Typography>
            <Slider
              size="small"
              min={1}
              max={20}
              value={minForwards}
              onChange={(_, v) => setMinForwards(v)}
              valueLabelDisplay="auto"
            />
          </Box>
          <FormControlLabel
            control={
              <Switch
                checked={onlyMonitored}
                onChange={(e) => setOnlyMonitored(e.target.checked)}
                size="small"
              />
            }
            label="Solo monitorizados"
          />
          <FormControlLabel
            control={
              <Switch
                checked={includeDiscontinued}
                onChange={(e) => setIncludeDiscontinued(e.target.checked)}
                size="small"
              />
            }
            label="Incluir descontinuados"
          />
        </Stack>
      </Paper>

      {graphError && (
        <Alert severity="error" sx={{ mb: 2 }}>{graphError}</Alert>
      )}

      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: { xs: '1fr', md: '1fr 340px' },
          gap: 2,
          alignItems: 'stretch',
          minHeight: 540,
        }}
      >
        <Paper variant="outlined" sx={{ p: 1, position: 'relative', overflow: 'hidden' }}>
          {loadingGraph ? (
            <Box display="flex" justifyContent="center" alignItems="center" height={520}>
              <CircularProgress />
            </Box>
          ) : (
            <ChannelGraph
              nodes={visibleGraph.nodes}
              edges={visibleGraph.edges}
              selectedId={selectedId}
              highlightQuery={search}
              onSelectNode={handleSelectNode}
              height={520}
            />
          )}
          {!loadingGraph && visibleGraph.nodes.length === 0 && (
            <Box position="absolute" inset={0} display="flex" alignItems="center" justifyContent="center" p={3}>
              <Typography color="text.secondary" align="center">
                No hay nodos para mostrar. Comprueba que el scraper haya rellenado
                monitored_channels / channel_edges.
              </Typography>
            </Box>
          )}
        </Paper>

        {!isMobile && (
          <Paper variant="outlined" sx={{ p: 2, overflow: 'auto', maxHeight: 560 }}>
            {panel}
          </Paper>
        )}
      </Box>

      <Stack direction="row" spacing={2} mt={1.5} flexWrap="wrap">
        <LegendDot color="#1976d2" label="Activo" />
        <LegendDot color="#d32f2f" label="Error / descontinuado" />
        <LegendDot color="#ed6c02" label="Solo en grafo" />
      </Stack>

      <Drawer
        anchor="bottom"
        open={isMobile && drawerOpen}
        onClose={() => setDrawerOpen(false)}
        PaperProps={{ sx: { maxHeight: '75vh', borderTopLeftRadius: 12, borderTopRightRadius: 12, p: 2 } }}
      >
        <Box display="flex" justifyContent="flex-end">
          <IconButton onClick={() => setDrawerOpen(false)} aria-label="Cerrar">
            <CloseIcon />
          </IconButton>
        </Box>
        {panel}
      </Drawer>
    </Container>
  );
};

function LegendDot({ color, label }) {
  return (
    <Stack direction="row" spacing={0.75} alignItems="center">
      <Box sx={{ width: 10, height: 10, borderRadius: '50%', bgcolor: color }} />
      <Typography variant="caption" color="text.secondary">{label}</Typography>
    </Stack>
  );
}

export default ChannelsPage;
