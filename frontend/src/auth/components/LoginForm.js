import React, { useState } from 'react';
import { Navigate } from 'react-router-dom';
import {
  Container,
  Paper,
  TextField,
  Button,
  Typography,
  Box,
  Alert,
  Link,
} from '@mui/material';
import { useAuth } from '../AuthContext';
import OAuthButtons from './OAuthButtons';
import logo from '../../assets/Logo_MonitorIA ajustado.png';
import config from '../../config';

const LoginForm = () => {
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');
  const [info, setInfo] = useState('');
  const [devLink, setDevLink] = useState('');
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const { user, requestMagicLink } = useAuth();

  if (user) {
    return <Navigate to="/" replace />;
  }

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      setError('');
      setInfo('');
      setDevLink('');
      setLoading(true);
      const data = await requestMagicLink(email.trim());
      setSent(true);
      setInfo(data.message || 'Revisa tu correo para continuar.');
      if (data.dev_magic_link) {
        setDevLink(data.dev_magic_link);
      }
    } catch (err) {
      setError(err.response?.data?.error || 'No se pudo solicitar el acceso');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Container maxWidth="sm">
      <Box sx={{ mt: 8, mb: 4 }}>
        <Box sx={{ textAlign: 'center', mb: 3 }}>
          <Box
            component="img"
            src={logo}
            alt="MonitorIA"
            sx={{ width: 160, height: 'auto', mb: 1 }}
          />
          <Typography variant="caption" color="text.secondary" display="block">
            v {config.APP_VERSION}
          </Typography>
        </Box>

        <Paper elevation={2} sx={{ p: 4 }}>
          <Typography variant="h5" component="h1" gutterBottom align="center">
            Acceder a MonitorIA
          </Typography>
          <Typography variant="body2" color="text.secondary" align="center" sx={{ mb: 3 }}>
            Introduce tu correo autorizado. Te enviaremos un enlace de un solo uso.
          </Typography>

          {error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
          )}

          {info && (
            <Alert severity="success" sx={{ mb: 2 }}>
              {info}
            </Alert>
          )}

          {devLink && (
            <Alert severity="info" sx={{ mb: 2 }}>
              Modo desarrollo —{' '}
              <Link href={devLink} underline="hover">
                abrir magic link
              </Link>
            </Alert>
          )}

          <form onSubmit={handleSubmit}>
            <TextField
              fullWidth
              label="Email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              margin="normal"
              required
              autoFocus
              autoComplete="email"
              disabled={loading}
            />

            <Button
              type="submit"
              fullWidth
              variant="contained"
              color="primary"
              size="large"
              disabled={loading || !email.trim()}
              sx={{ mt: 2 }}
            >
              {loading ? 'Enviando…' : sent ? 'Reenviar enlace' : 'Enviar enlace de acceso'}
            </Button>
          </form>

          <OAuthButtons />
        </Paper>
      </Box>
    </Container>
  );
};

export default LoginForm;
