import React, { useEffect, useState } from 'react';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import Dashboard from './components/Dashboard';

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
  const [filters, setFilters] = useState({});
  const [buildId, setBuildId] = useState('');

  const handleFilterChange = (newFilters) => {
    setFilters(newFilters);
  };

  useEffect(() => {
    let isMounted = true;
    fetch('/build-id.txt', { cache: 'no-store' })
      .then((response) => (response.ok ? response.text() : ''))
      .then((text) => {
        if (isMounted && text) {
          setBuildId(text.trim());
        }
      })
      .catch(() => {});
    return () => {
      isMounted = false;
    };
  }, []);

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      {buildId && (
        <Box sx={{ py: 1, textAlign: 'center' }}>
          <Typography variant="caption" color="textSecondary" display="block">
            Build: {buildId}
          </Typography>
        </Box>
      )}
      <Dashboard />
    </ThemeProvider>
  );
}

export default App;
