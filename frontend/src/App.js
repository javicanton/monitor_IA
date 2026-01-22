import React, { useState } from 'react';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import Container from '@mui/material/Container';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import MessageList from './components/MessageList';
import FilterBar from './components/FilterBar';
import ScoreExplanation from './components/ScoreExplanation';

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

  const handleFilterChange = (newFilters) => {
    setFilters(newFilters);
  };

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Container maxWidth="xl">
        <Box sx={{ my: 4 }}>
          <Typography variant="h3" component="h1" gutterBottom align="center">
            Overperforming Messages in Telegram
          </Typography>
          
          <ScoreExplanation />
          
          <Typography variant="h4" component="h2" gutterBottom align="center">
            Label messages as relevant or not relevant
          </Typography>

          <FilterBar onFilterChange={handleFilterChange} />
          
          <MessageList filters={filters} />
        </Box>
      </Container>
    </ThemeProvider>
  );
}

export default App;
