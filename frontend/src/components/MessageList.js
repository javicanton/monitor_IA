import React, { useState, useEffect, useCallback } from 'react';
import { 
  Box, 
  Grid, 
  CircularProgress, 
  Typography, 
  Button, 
  Alert,
  Snackbar 
} from '@mui/material';
import { Refresh as RefreshIcon } from '@mui/icons-material';
import MessageCard from './MessageCard';
import { messagesAPI } from '../utils/api';

const MessageList = ({ filters = {} }) => {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [hasMore, setHasMore] = useState(true);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalMessages, setTotalMessages] = useState(0);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'info' });

  const MESSAGES_PER_PAGE = 24;
 
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
        
        setTotalMessages(response.total_messages || 0);
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
    fetchMessages(1, false);
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
        // Actualizar el mensaje en el estado local
        setMessages(prev => 
          prev.map(msg => 
            msg['Message ID'] === messageId ? { ...msg, Label: label } : msg
          )
        );
        
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
    fetchMessages(1, false);
  };

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
        <Typography variant="h6" color="textSecondary">
          {totalMessages > 0 ? `${totalMessages} mensajes encontrados` : 'Sin mensajes'}
        </Typography>
        
        <Box display="flex" gap={2}>
          <Button
            variant="outlined"
            onClick={handleRefresh}
            startIcon={<RefreshIcon />}
            disabled={loading}
          >
            Actualizar
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
                Embed: message['Embed']
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
