import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Alert,
  Box,
  Button,
  Container,
  FormControl,
  FormControlLabel,
  InputLabel,
  MenuItem,
  Paper,
  Select,
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
import ChannelGraph, { LAYOUT_OPTIONS } from './ChannelGraph';
import ChannelDetailPanel from './ChannelDetailPanel';
import logo from '../../assets/Logo_MonitorIA ajustado.png';

const ChannelsPage = () => {
  const { logout, user } = useAuth();
  const navigate = useNavigate();
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const isAdmin = user?.role === 'admin';

  const [graph, setGraph] = useState({ nodes: [], edges: [], meta: null });
  const [loadingGraph, setLoadingGraph] = useState(true);
  const [graphError, setGraphError] = useState('');
  const [search, setSearch] = useState('');
  const [filterBySearch, setFilterBySearch] = useState(true);
  const [minForwards, setMinForwards] = useState(1);
  const [nodeSizeScale, setNodeSizeScale] = useState(0.7);
  const [onlyMonitored, setOnlyMonitored] = useState(false);
  const [includeDiscontinued, setIncludeDiscontinued] = useState(true);
  const [layout, setLayout] = useState('forceAtlas2');
  const [showClusters, setShowClusters] = useState(false);

  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [days, setDays] = useState(30);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [monitorBusy, setMonitorBusy] = useState(false);
  const [monitorMsg, setMonitorMsg] = useState('');

  const graphHeight = isMobile
    ? Math.max(420, Math.min(window.innerHeight * 0.55, 640))
    : Math.max(560, Math.min(window.innerHeight - 220, 820));

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

  // Filtros cliente: quitan nodos sin cambiar el algoritmo de layout
  const visibleGraph = useMemo(() => {
    let nodes = graph.nodes;
    if (onlyMonitored) {
      nodes = nodes.filter((n) => n.monitored);
    }
    const q = search.trim().toLowerCase();
    if (filterBySearch && q) {
      nodes = nodes.filter(
        (n) =>
          (n.username || '').toLowerCase().includes(q)
          || (n.title || '').toLowerCase().includes(q)
      );
    }
    const ids = new Set(nodes.map((n) => n.id));
    const edges = graph.edges.filter((e) => ids.has(e.source) && ids.has(e.target));
    return { nodes, edges };
  }, [graph, onlyMonitored, filterBySearch, search]);

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

  // Si el nodo seleccionado desaparece del filtro, limpiar selección
  useEffect(() => {
    if (selectedId && !visibleGraph.nodes.some((n) => n.id === selectedId)) {
      setSelectedId(null);
    }
  }, [visibleGraph.nodes, selectedId]);

  const handleSelectNode = (node) => {
    const id = node?.id || node?.username || null;
    setSelectedId(id);
    setMonitorMsg('');
    if (isMobile && id) setDrawerOpen(true);
  };

  const handleSelectNeighbor = (username) => {
    setSelectedId(username);
    setMonitorMsg('');
    if (isMobile) setDrawerOpen(true);
  };

  const handleSearchApply = () => {
    const q = search.trim().toLowerCase();
    if (!q) return;
    // Activar filtro (elimina nodos del grafo, sin cambiar layout)
    setFilterBySearch(true);
    const match = graph.nodes.find(
      (n) =>
        (n.username || '').toLowerCase().includes(q)
        || (n.title || '').toLowerCase().includes(q)
    );
    if (match) {
      setSelectedId(match.id);
      if (isMobile) setDrawerOpen(true);
    }
  };

  const handleViewMessages = (channel) => {
    const title = channel?.title || channel?.username;
    if (!title) return;
    navigate(`/?channel=${encodeURIComponent(title)}`);
  };

  const handleMonitor = async (channel) => {
    if (!channel?.username) return;
    try {
      setMonitorBusy(true);
      setMonitorMsg('');
      const res = await channelsAPI.monitorChannel({
        username: channel.username,
        title: channel.title,
      });
      setMonitorMsg(res.message || (res.action === 'added' ? 'Añadido' : 'Propuesta enviada'));
      if (res.action === 'added') {
        await loadGraph();
        await loadDetail(channel.username, days);
      }
    } catch (err) {
      setMonitorMsg(err.response?.data?.error || err.message || 'No se pudo completar');
    } finally {
      setMonitorBusy(false);
    }
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
      meta={{
        ...graph.meta,
        visible_nodes: visibleGraph.nodes.length,
        visible_edges: visibleGraph.edges.length,
      }}
      selectedUsername={selectedId}
      detail={detail}
      loading={loadingDetail}
      days={days}
      onDaysChange={setDays}
      onSelectNeighbor={handleSelectNeighbor}
      onViewMessages={handleViewMessages}
      onMonitor={handleMonitor}
      monitorBusy={monitorBusy}
      monitorMsg={monitorMsg}
      isAdmin={isAdmin}
    />
  );

  return (
    <Container maxWidth={false} sx={{ py: 2, px: { xs: 1.5, md: 3 } }}>
      <UserMenu onLogout={handleLogout} />

      <Stack direction="row" alignItems="center" spacing={2} mb={1.5} flexWrap="wrap">
        <Box
          component="img"
          src={logo}
          alt="MonitorIA"
          sx={{ width: 48, height: 'auto', cursor: 'pointer' }}
          onClick={() => navigate('/')}
        />
        <Box flex={1} minWidth={160}>
          <Typography variant="h5" sx={{ fontWeight: 600 }}>Canales</Typography>
          <Typography variant="body2" color="text.secondary">
            Grafo de reenvíos · {LAYOUT_OPTIONS.find((o) => o.value === layout)?.label}
            {showClusters ? ' · clusters' : ''}
          </Typography>
        </Box>
        <Button startIcon={<ArrowBackIcon />} onClick={() => navigate('/')} size="small">
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

      <Paper variant="outlined" sx={{ p: 1.5, mb: 1.5 }}>
        <Stack
          direction={{ xs: 'column', md: 'row' }}
          spacing={1.5}
          alignItems={{ md: 'center' }}
          flexWrap="wrap"
        >
          <TextField
            size="small"
            label="Buscar canal"
            placeholder="@username o título · Enter filtra"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearchApply()}
            sx={{ minWidth: { md: 220 }, flex: 1 }}
          />
          <Button size="small" variant="contained" onClick={handleSearchApply}>
            Ir
          </Button>
          <Button
            size="small"
            variant="text"
            disabled={!search && !filterBySearch}
            onClick={() => {
              setSearch('');
              setFilterBySearch(false);
            }}
          >
            Limpiar filtro
          </Button>
          <FormControl size="small" sx={{ minWidth: 160 }}>
            <InputLabel id="layout-label">Layout</InputLabel>
            <Select
              labelId="layout-label"
              label="Layout"
              value={layout}
              onChange={(e) => setLayout(e.target.value)}
            >
              {LAYOUT_OPTIONS.map((opt) => (
                <MenuItem key={opt.value} value={opt.value}>{opt.label}</MenuItem>
              ))}
            </Select>
          </FormControl>
          <Box sx={{ width: { xs: '100%', md: 150 }, px: 1 }}>
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
          <Box sx={{ width: { xs: '100%', md: 150 }, px: 1 }}>
            <Typography variant="caption" color="text.secondary">
              Tamaño nodos: {nodeSizeScale.toFixed(1)}
            </Typography>
            <Slider
              size="small"
              min={0.3}
              max={2}
              step={0.1}
              value={nodeSizeScale}
              onChange={(_, v) => setNodeSizeScale(v)}
              valueLabelDisplay="auto"
            />
          </Box>
          <FormControlLabel
            control={
              <Switch
                checked={filterBySearch}
                onChange={(e) => setFilterBySearch(e.target.checked)}
                size="small"
              />
            }
            label="Filtrar búsqueda"
          />
          <FormControlLabel
            control={
              <Switch
                checked={showClusters}
                onChange={(e) => setShowClusters(e.target.checked)}
                size="small"
              />
            }
            label="Clusters"
          />
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
            label="Descontinuados"
          />
        </Stack>
      </Paper>

      {graphError && (
        <Alert severity="error" sx={{ mb: 2 }}>{graphError}</Alert>
      )}

      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: { xs: '1fr', md: 'minmax(0,1fr) 360px' },
          gap: 2,
          alignItems: 'stretch',
          minHeight: graphHeight,
        }}
      >
        <Paper
          variant="outlined"
          sx={{
            p: 1,
            position: 'relative',
            overflow: 'hidden',
            aspectRatio: { md: '1 / 1' },
            maxHeight: { md: graphHeight + 40 },
            minHeight: graphHeight,
          }}
        >
          {loadingGraph ? (
            <Box display="flex" justifyContent="center" alignItems="center" height="100%" minHeight={graphHeight}>
              <CircularProgress />
            </Box>
          ) : (
            <ChannelGraph
              nodes={visibleGraph.nodes}
              edges={visibleGraph.edges}
              selectedId={selectedId}
              highlightQuery={filterBySearch ? '' : search}
              layout={layout}
              nodeSizeScale={nodeSizeScale}
              showClusters={showClusters}
              onSelectNode={handleSelectNode}
              height={graphHeight}
            />
          )}
          {!loadingGraph && visibleGraph.nodes.length === 0 && (
            <Box
              position="absolute"
              top={0}
              left={0}
              right={0}
              bottom={0}
              display="flex"
              alignItems="center"
              justifyContent="center"
              p={3}
            >
              <Typography color="text.secondary" align="center">
                No hay nodos con los filtros actuales. Prueba «Limpiar filtro» o baja el mínimo de reenvíos.
              </Typography>
            </Box>
          )}
        </Paper>

        {!isMobile && (
          <Paper variant="outlined" sx={{ p: 2, overflow: 'auto', maxHeight: graphHeight + 48 }}>
            {panel}
          </Paper>
        )}
      </Box>

      <Stack direction="row" spacing={2} mt={1.5} flexWrap="wrap" alignItems="center">
        {!showClusters && (
          <>
            <LegendDot color="#1976d2" label="Activo" />
            <LegendDot color="#d32f2f" label="Error / descontinuado" />
            <LegendDot color="#ed6c02" label="Solo en grafo" />
          </>
        )}
        {showClusters && (
          <Typography variant="caption" color="text.secondary">
            Colores = clusters (modularidad / label propagation).
          </Typography>
        )}
        <Typography variant="caption" color="text.secondary">
          Filtrar quita nodos y mantiene posiciones. Cambiar layout sí redistribuye.
          Visible: {visibleGraph.nodes.length} nodos / {visibleGraph.edges.length} aristas.
        </Typography>
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
