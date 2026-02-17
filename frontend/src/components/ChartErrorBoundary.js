import React from 'react';
import { Paper, Typography, Button } from '@mui/material';

/**
 * Error boundary para el gráfico: si Recharts u otro falla, mostramos un mensaje
 * en lugar de dejar la pantalla en blanco.
 */
class ChartErrorBoundary extends React.Component {
  state = { hasError: false, error: null };

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('ChartErrorBoundary:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <Paper sx={{ p: 2, mb: 3 }} elevation={0} variant="outlined">
          <Typography color="textSecondary" gutterBottom>
            No se pudo mostrar el gráfico de evolución.
          </Typography>
          <Button
            size="small"
            onClick={() => this.setState({ hasError: false, error: null })}
          >
            Reintentar
          </Button>
        </Paper>
      );
    }
    return this.props.children;
  }
}

export default ChartErrorBoundary;
