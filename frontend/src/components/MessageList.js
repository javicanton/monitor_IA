import React, { useState, useEffect, useCallback, useRef } from 'react';
import { 
  Box, 
  Grid, 
  CircularProgress, 
  Typography, 
  Button, 
  Alert,
  Snackbar,
} from '@mui/material';
import {
  Refresh as RefreshIcon,
  Download as DownloadIcon,
} from '@mui/icons-material';
import MessageCard from './MessageCard';
import { messagesAPI, channelsAPI } from '../utils/api';
import config from '../config';

const DEBOUNCE_MS = 500;

const getLoadingMessage = (filters = {}) => {
  const search = (filters.search || '').trim();
  if (search) {
    return `Buscando «${search}» en el texto del mensaje y el enlace…`;
  }
  if (filters.dateStart || filters.dateEnd) {
    return 'Aplicando filtro de fechas…';
  }
  if (filters.channel?.length || filters.excludeChannel?.length || filters.topics?.length) {
    return 'Aplicando filtros de canal o temas…';
  }
  return 'Cargando mensajes…';
};

const MessageList = ({ filters = {}, onLoadingChange, onStatsChange }) => {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [hasMore, setHasMore] = useState(true);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalMessages, setTotalMessages] = useState(0);
  const [totalChannels, setTotalChannels] = useState(0);
  const [showNotRelevant, setShowNotRelevant] = useState(false);
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
        excludeNotRelevant: !showNotRelevant,
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
  }, [filters, showNotRelevant, MESSAGES_PER_PAGE]);

  useEffect(() => {
    onLoadingChange?.(loading);
  }, [loading, onLoadingChange]);

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
        if (label === config.LABELS.NOT_RELEVANT && !showNotRelevant) {
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

  const handleRefresh = useCallback(() => {
    fetchChannelCount();
    fetchMessages(1, false);
  }, [fetchChannelCount, fetchMessages]);

  useEffect(() => {
    fetchChannelCount();
  }, [fetchChannelCount]);

  useEffect(() => {
    onStatsChange?.({
      totalMessages,
      totalChannels,
      loading,
      onRefresh: handleRefresh,
    });
  }, [totalMessages, totalChannels, loading, onStatsChange, handleRefresh]);

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
      const response = await messagesAPI.downloadFilteredCSV({
        ...filters,
        excludeNotRelevant: !showNotRelevant,
      });
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
      <Box
        display="flex"
        flexDirection="column"
        justifyContent="center"
        alignItems="center"
        minHeight="200px"
        sx={{ mt: 4 }}
      >
        <CircularProgress />
        <Typography variant="body1" sx={{ mt: 2 }}>
          {getLoadingMessage(filters)}
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
          Puede tardar unos segundos con búsquedas o filtros amplios.
        </Typography>
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
    <Box>
      {loading && (
        <Alert severity="info" sx={{ mb: 2 }}>
          <Box display="flex" alignItems="flex-start" gap={1.5}>
            <CircularProgress size={18} sx={{ mt: 0.25, flexShrink: 0 }} />
            <Box>
              <Typography variant="body2">{getLoadingMessage(filters)}</Typography>
              <Typography variant="caption" color="text.secondary">
                Espera un momento; el proceso sigue en curso.
              </Typography>
            </Box>
          </Box>
        </Alert>
      )}
      {/* Acciones debajo del buscador y del recuento: una sola fila */}
      <Box
        display="grid"
        gridTemplateColumns="repeat(4, minmax(0, 1fr))"
        gap={1}
        alignItems="stretch"
        mb={3}
      >
          <Button
            variant="outlined"
            size="small"
            onClick={handleDownloadMessages}
            startIcon={<DownloadIcon />}
            disabled={loading}
            sx={{ whiteSpace: 'nowrap', minWidth: 0 }}
          >
            Descargar mensajes
          </Button>
          <Button
            variant="outlined"
            size="small"
            onClick={handleDownloadChannels}
            startIcon={<DownloadIcon />}
            disabled={loading}
            sx={{ whiteSpace: 'nowrap', minWidth: 0 }}
          >
            Descargar canales
          </Button>
          <Button
            variant="outlined"
            size="small"
            onClick={() => setShowNotRelevant((prev) => !prev)}
            disabled={loading}
            sx={{ whiteSpace: 'nowrap', minWidth: 0 }}
          >
            {showNotRelevant ? 'Ocultar no relevantes' : 'Mostrar no relevantes'}
          </Button>
          <Button
            variant="contained"
            color="secondary"
            size="small"
            onClick={handleExportRelevants}
            disabled={loading}
            sx={{ whiteSpace: 'nowrap', minWidth: 0 }}
          >
            Exportar Relevantes
          </Button>
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
