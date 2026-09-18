import React from 'react';
import { Box, Button, Typography, Stack } from '@mui/material';
import GoogleIcon from '@mui/icons-material/Google';
import GitHubIcon from '@mui/icons-material/GitHub';

/**
 * Botones OAuth preparados para fase 2 (Google / GitHub).
 * Deshabilitados hasta que REACT_APP_OAUTH_ENABLED=true y el backend esté listo.
 */
const OAuthButtons = () => {
  const enabled = process.env.REACT_APP_OAUTH_ENABLED === 'true';

  if (!enabled) {
    return (
      <Box sx={{ mt: 3, textAlign: 'center' }}>
        <Typography variant="caption" color="text.secondary">
          Próximamente: acceso con Google y GitHub
        </Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ mt: 3 }}>
      <Typography variant="body2" color="text.secondary" align="center" sx={{ mb: 1.5 }}>
        O continúa con
      </Typography>
      <Stack spacing={1}>
        <Button
          fullWidth
          variant="outlined"
          startIcon={<GoogleIcon />}
          href="/api/auth/oauth/google"
        >
          Google
        </Button>
        <Button
          fullWidth
          variant="outlined"
          startIcon={<GitHubIcon />}
          href="/api/auth/oauth/github"
        >
          GitHub
        </Button>
      </Stack>
    </Box>
  );
};

export default OAuthButtons;
