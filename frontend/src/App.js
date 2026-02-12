import React from 'react';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import Dashboard from './components/Dashboard';
import config from './config';

const theme = createTheme({
  palette: {
    primary: {
      main: '#007bff',
    },
    secondary: {
      main: '#6c757d',
    },
  },
});

function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Box sx={{ py: 1, textAlign: 'center' }}>
        <Typography variant="caption" color="textSecondary" display="block">
          v {config.APP_VERSION}
        </Typography>
      </Box>
      <Dashboard />
    </ThemeProvider>
  );
}

export default App;
