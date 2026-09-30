import React, { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Container, Box, CircularProgress, Alert, Typography, Button } from '@mui/material';
import { useAuth } from '../AuthContext';

const VerifyMagicLinkPage = () => {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token') || '';
  const { verifyMagicLink, user } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState('');
  const [done, setDone] = useState(false);

  useEffect(() => {
    let cancelled = false;

    const run = async () => {
      if (!token) {
        setError('Enlace no válido');
        return;
      }
      if (user) {
        navigate('/', { replace: true });
        return;
      }
      try {
        await verifyMagicLink(token);
        if (!cancelled) {
          setDone(true);
          navigate('/', { replace: true });
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err.response?.data?.error || 'No se pudo verificar el enlace de acceso'
          );
        }
      }
    };

    run();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  return (
    <Container maxWidth="sm">
      <Box sx={{ mt: 10, textAlign: 'center' }}>
        {!error && !done && (
          <>
            <CircularProgress sx={{ mb: 2 }} />
            <Typography>Verificando acceso…</Typography>
          </>
        )}
        {error && (
          <>
            <Alert severity="error" sx={{ mb: 2, textAlign: 'left' }}>
              {error}
            </Alert>
            <Button variant="contained" onClick={() => navigate('/login', { replace: true })}>
              Volver al login
            </Button>
          </>
        )}
      </Box>
    </Container>
  );
};

export default VerifyMagicLinkPage;
