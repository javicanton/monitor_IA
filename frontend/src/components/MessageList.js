import React, { useState, useEffect, useCallback, useRef } from 'react';
import { 
  Box, 
  Grid, 
  CircularProgress, 
  Typography, 
  Button, 
  Alert,
  Snackbar,
  Tooltip,
} from '@mui/material';
import {
  Refresh as RefreshIcon,
  Download as DownloadIcon,
  Article as ArticleIcon,
  Campaign as CampaignIcon,
} from '@mui/icons-material';
import MessageCard from './MessageCard';
import { messagesAPI, channelsAPI } from '../utils/api';
import config from '../config';

const formatPublicationCount = (count) => {
  const n = Number(count);
  if (!Number.isFinite(n)) return '0';
  return new Intl.NumberFormat('es-ES').format(n);
};

const DEBOUNCE_MS = 500;

const MessageList = ({ filters = {} }) => {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [hasMore, setHasMore] = useState(true);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalMessages, setTotalMessages] = useState(0);
  const [totalChannels, setTotalChannels] = useState(0);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'info' });
  const debounceRef = useRef(null);
  const isFirstLoad = useRef(true);

  const MESSAGES_PER_PAGE = 24;

  const fetchChannelCount = useCallback(async () => {
    try {
      const channels = await channelsAPI.getChannels();
      setTotalChannels(channels.length);
    } catch (err) {
      console.error('Error al cargar conteo de canales:', err);
    }
  }, []);

  const fetchMessages = useCallback(async (page = 1, append = false) => {
    try {
      setLoading(true);
      setError(null);

      const response = await messagesAPI.getMessages({
        ...filters,
        page,
        per_page: MESSAGES_PER_PAGE
      });

      if (response.success) {
        const newMessages = response.messages || [];
        
        if (append) {
          setMessages(prev => [...prev, ...newMessages]);
        } else {
          setMessages(newMessages);
        }
        
        setTotalMessages(Number(response.total_messages) || 0);
        setCurrentPage(page);
        setHasMore(newMessages.length === MESSAGES_PER_PAGE);
        
        if (newMessages.length === 0 && page === 1) {
          setSnackbar({
            open: true,
            message: 'No se encontraron mensajes con los filtros aplicados',
            severity: 'info'
          });
        }
      } else {
        throw new Error(response.error || 'Error al cargar los mensajes');
      }
    } catch (err) {
      console.error('Error al cargar mensajes:', err);
      setError(err.message);
      setSnackbar({
        open: true,
        message: `Error al cargar mensajes: ${err.message}`,
        severity: 'error'
      });
    } finally {
      setLoading(false);
    }
  }, [filters, MESSAGES_PER_PAGE]);

  useEffect(() => {
    if (isFirstLoad.current) {
      isFirstLoad.current = false;
      fetchMessages(1, false);
      return;
    }
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      fetchMessages(1, false);
      debounceRef.current = null;
    }, DEBOUNCE_MS);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [fetchMessages]);

  const loadMore = async () => {
    if (!hasMore || loading) return;
    
    const nextPage = currentPage + 1;
    await fetchMessages(nextPage, true);
  };

  const handleLabel = async (messageId, label) => {
    try {
      const response = await messagesAPI.labelMessage(messageId, label);
      
      if (response.success) {
        if (label === config.LABELS.NOT_RELEVANT) {
          setMessages((prev) => prev.filter((msg) => msg['Message ID'] !== messageId));
          setTotalMessages((prev) => Math.max(0, prev - 1));
        } else {
          setMessages((prev) =>
            prev.map((msg) =>
              msg['Message ID'] === messageId ? { ...msg, Label: label } : msg
            )
          );
        }

        setSnackbar({
          open: true,
          message: 'Mensaje etiquetado correctamente',
          severity: 'success'
        });
      } else {
        throw new Error(response.error || 'Error al etiquetar el mensaje');
      }
    } catch (err) {
      console.error('Error al etiquetar:', err);
      setSnackbar({
        open: true,
        message: `Error al etiquetar: ${err.message}`,
        severity: 'error'
      });
    }
  };

  const handleRefresh = () => {
    fetchChannelCount();
    fetchMessages(1, false);
  };

  useEffect(() => {
    fetchChannelCount();
  }, [fetchChannelCount]);

  const handleExportRelevants = async () => {
    try {
      const response = await messagesAPI.exportRelevants();
      
      if (response.success) {
        setSnackbar({
          open: true,
          message: response.message || 'Mensajes relevantes exportados correctamente',
          severity: 'success'
        });
      } else {
        throw new Error(response.error || 'Error al exportar mensajes relevantes');
      }
    } catch (err) {
      console.error('Error al exportar:', err);
      setSnackbar({
        open: true,
        message: `Error al exportar: ${err.message}`,
        severity: 'error'
      });
    }
  };

  const handleDownloadChannels = async () => {
    try {
      const response = await channelsAPI.downloadChannelGraph();
      const blob = new Blob([response.data], { type: 'application/zip' });
      const disposition = response.headers['content-disposition'];
      let filename = 'channel_graph.zip';
      if (disposition && disposition.includes('filename=')) {
        const match = disposition.match(/filename[*]?=['"]?(?:UTF-8'')?([^;\n"']+)['"]?/i);
        if (match) filename = match[1].trim();
      }
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      setSnackbar({
        open: true,
        message: 'Descarga de canales iniciada',
        severity: 'success'
      });
    } catch (err) {
      console.error('Error al descargar canales:', err);
      setSnackbar({
        open: true,
        message: `Error al descargar canales: ${err.response?.data?.error || err.message}`,
        severity: 'error'
      });
    }
  };

  const handleDownloadMessages = async () => {
    try {
      const response = await messagesAPI.downloadFilteredCSV(filters);
      const blob = new Blob([response.data], { type: 'text/csv;charset=utf-8;' });
      const disposition = response.headers['content-disposition'];
      let filename = 'mensajes_filtrados.csv';
      if (disposition && disposition.includes('filename=')) {
        const match = disposition.match(/filename[*]?=['"]?(?:UTF-8'')?([^;\n"']+)['"]?/i);
        if (match) filename = match[1].trim();
      }
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      setSnackbar({
        open: true,
        message: 'Descarga iniciada',
        severity: 'success'
      });
    } catch (err) {
      console.error('Error al descargar:', err);
      setSnackbar({
        open: true,
        message: `Error al descargar: ${err.message}`,
        severity: 'error'
      });
    }
  };

  const handleCloseSnackbar = () => {
    setSnackbar({ ...snackbar, open: false });
  };

  if (loading && messages.length === 0) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="200px">
        <CircularProgress />
      </Box>
    );
  }

  if (error && messages.length === 0) {
    return (
      <Box display="flex" flexDirection="column" alignItems="center" minHeight="200px">
        <Typography color="error" variant="h6" gutterBottom>
          Error al cargar los mensajes
        </Typography>
        <Typography color="textSecondary" gutterBottom>
          {error}
        </Typography>
        <Button 
          variant="contained" 
          onClick={handleRefresh}
          startIcon={<RefreshIcon />}
        >
          Reintentar
        </Button>
      </Box>
    );
  }

  return (
    <Box sx={{ mt: 4 }}>
      {/* Header con estadísticas y botones */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Tooltip
          title={`${formatPublicationCount(totalMessages)} publicaciones · ${formatPublicationCount(totalChannels)} canales (clic para actualizar)`}
        >
          <Button
            variant="outlined"
            onClick={handleRefresh}
            disabled={loading}
            aria-label={`${totalMessages} publicaciones, ${totalChannels} canales`}
            sx={{
              textTransform: 'none',
              color: 'text.secondary',
              borderColor: 'divider',
              px: 2,
              py: 1,
            }}
          >
            <Box display="flex" alignItems="center" gap={1.5}>
              <Box display="flex" alignItems="center" gap={0.5} component="span">
                <ArticleIcon fontSize="small" color="action" aria-hidden />
                <Typography variant="body1" component="span" fontWeight={500}>
                  {formatPublicationCount(totalMessages)}
                </Typography>
              </Box>
              <Box
                component="span"
                sx={{ width: '1px', height: 20, bgcolor: 'divider' }}
                aria-hidden
              />
              <Box display="flex" alignItems="center" gap={0.5} component="span">
                <CampaignIcon fontSize="small" color="action" aria-hidden />
                <Typography variant="body1" component="span" fontWeight={500}>
                  {formatPublicationCount(totalChannels)}
                </Typography>
              </Box>
            </Box>
          </Button>
        </Tooltip>
        
        <Box display="flex" gap={2}>
          <Button
            variant="outlined"
            onClick={handleDownloadMessages}
            startIcon={<DownloadIcon />}
            disabled={loading}
          >
            Descargar mensajes
          </Button>
          <Button
            variant="outlined"
            onClick={handleDownloadChannels}
            startIcon={<DownloadIcon />}
            disabled={loading}
          >
            Descargar canales
          </Button>
          <Button
            variant="contained"
            color="secondary"
            onClick={handleExportRelevants}
            disabled={loading}
          >
            Exportar Relevantes
          </Button>
        </Box>
      </Box>

      {/* Lista de mensajes */}
      <Grid container spacing={2}>
        {messages.map((message) => (
          <Grid item xs={12} md={6} lg={4} key={message['Message ID']}>
            <MessageCard 
              message={{
                Score: message['Score'] || 0,
                Message_ID: message['Message ID'],
                URL: message['URL'],
                Label: message['Label'],
                Embed: message['Embed'],
                Topic_ID: message['topic_id'],
                Topic_Title: message['topic_title']
              }}
              onLabelChange={handleLabel}
            />
          </Grid>
        ))}
      </Grid>

      {/* Botón para cargar más */}
      {hasMore && (
        <Box display="flex" justifyContent="center" mt={4}>
          <Button
            variant="outlined"
            onClick={loadMore}
            disabled={loading}
            size="large"
          >
            {loading ? <CircularProgress size={20} /> : 'Cargar Más Mensajes'}
          </Button>
        </Box>
      )}

      {/* Mensaje cuando no hay más mensajes */}
      {!hasMore && messages.length > 0 && (
        <Box textAlign="center" mt={4}>
          <Typography color="textSecondary">
            No hay más mensajes para cargar
          </Typography>
        </Box>
      )}

      {/* Snackbar para notificaciones */}
      <Snackbar
        open={snackbar.open}
        autoHideDuration={6000}
        onClose={handleCloseSnackbar}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      >
        <Alert 
          onClose={handleCloseSnackbar} 
          severity={snackbar.severity}
          sx={{ width: '100%' }}
        >
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default MessageList;
