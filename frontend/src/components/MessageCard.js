import React, { useEffect, useRef } from 'react';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Typography from '@mui/material/Typography';
import Button from '@mui/material/Button';
import Box from '@mui/material/Box';
import Link from '@mui/material/Link';
import Chip from '@mui/material/Chip';

function MessageCard({ message, onLabelChange }) {
  const { Score, Message_ID, URL, Label, Embed, Topic_ID, Topic_Title } = message;
  const embedRef = useRef(null);

  useEffect(() => {
    if (embedRef.current && Embed) {
      // Limpiar el contenido anterior
      embedRef.current.innerHTML = '';
      
      // Crear el script de Telegram
      const script = document.createElement('script');
      script.async = true;
      script.src = 'https://telegram.org/js/telegram-widget.js?22';
      
      // Extraer el data-telegram-post del embed
      const match = Embed.match(/data-telegram-post="([^"]+)"/);
      if (match) {
        script.setAttribute('data-telegram-post', match[1]);
        script.setAttribute('data-width', '100%');
        
        // Agregar el script al contenedor
        embedRef.current.appendChild(script);
      }
    }
  }, [Embed]);

  return (
    <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <CardContent>
        <Typography variant="h6" component="div" align="center" gutterBottom>
          Overperforming Score: <span style={{ color: 'red' }}>{Score.toFixed(2)}x</span>
        </Typography>
        {(Topic_Title || Topic_ID !== undefined) && (
          <Box display="flex" justifyContent="center" mb={1}>
            <Chip
              label={Topic_Title || `Topic ${Topic_ID}`}
              size="small"
              color="secondary"
              variant="outlined"
            />
          </Box>
        )}

        <Box 
          ref={embedRef}
          sx={{ 
            mb: 2,
            minHeight: '200px',
            '& iframe': {
              width: '100%',
              border: 'none'
            }
          }}
        />

        <Box sx={{ display: 'flex', gap: 1, justifyContent: 'center', mt: 2 }}>
          <Button
            variant="contained"
            color={Label === 1 ? 'success' : 'primary'}
            onClick={() => onLabelChange(Message_ID, 1)}
          >
            Relevant
          </Button>
          <Button
            variant="contained"
            color={Label === 0 ? 'error' : 'primary'}
            onClick={() => onLabelChange(Message_ID, 0)}
          >
            Not Relevant
          </Button>
          <Link
            href={URL}
            target="_blank"
            rel="noopener noreferrer"
            sx={{ textDecoration: 'none' }}
          >
            <Button
              variant="contained"
              color="primary"
              fullWidth
            >
              Go to message
            </Button>
          </Link>
        </Box>
      </CardContent>
    </Card>
  );
}

export default MessageCard; 