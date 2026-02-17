import React, { useState, useEffect } from 'react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Brush,
} from 'recharts';
import { Box, Paper, Typography, CircularProgress, Alert } from '@mui/material';
import { messagesAPI } from '../utils/api';

/**
 * Gráfico de evolución del número de mensajes por día.
 * Permite seleccionar un rango de fechas (arrastrando en el gráfico o con el brush)
 * para usarlo como filtro de fechas (onDateRangeChange).
 */
const MessagesOverTimeChart = ({ onDateRangeChange }) => {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    const fetchData = async () => {
      try {
        setLoading(true);
        setError(null);
        const res = await messagesAPI.getMessagesOverTime();
        if (!cancelled && res.success && Array.isArray(res.data)) {
          setData(res.data);
        }
      } catch (err) {
        if (!cancelled) setError(err.message || 'Error al cargar datos');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    fetchData();
    return () => { cancelled = true; };
  }, []);

  const handleBrushChange = (range) => {
    if (!data.length || !onDateRangeChange) return;
    let startIndex, endIndex;
    if (typeof range === 'object' && range !== null && !Array.isArray(range)) {
      startIndex = range.startIndex;
      endIndex = range.endIndex;
    } else if (Array.isArray(range) && range.length >= 2) {
      startIndex = range[0];
      endIndex = range[1];
    } else {
      return;
    }
    if (startIndex == null || endIndex == null) return;
    const start = data[Math.min(Math.max(0, startIndex), data.length - 1)]?.date;
    const end = data[Math.min(Math.max(0, endIndex), data.length - 1)]?.date;
    if (start && end) onDateRangeChange(start, end);
  };

  if (loading) {
    return (
      <Paper sx={{ p: 2, mb: 3, minHeight: 280, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <CircularProgress />
      </Paper>
    );
  }

  if (error) {
    return (
      <Paper sx={{ p: 2, mb: 3 }}>
        <Alert severity="error">{error}</Alert>
      </Paper>
    );
  }

  if (!data.length) {
    return (
      <Paper sx={{ p: 2, mb: 3 }}>
        <Typography color="textSecondary">No hay datos de mensajes por fecha.</Typography>
      </Paper>
    );
  }

  return (
    <Paper sx={{ p: 2, mb: 3 }} elevation={0} variant="outlined">
      <Typography variant="subtitle1" color="textSecondary" gutterBottom>
        Evolución de mensajes — selecciona un rango para filtrar por fechas
      </Typography>
      <Box sx={{ width: '100%', height: 280 }}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart
            data={data}
            margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
          >
            <defs>
              <linearGradient id="colorCount" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#1976d2" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#1976d2" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 11 }}
              tickFormatter={(v) => {
                const d = new Date(v + 'T12:00:00');
                return d.toLocaleDateString('es-ES', { day: '2-digit', month: 'short' });
              }}
            />
            <YAxis allowDecimals={false} tick={{ fontSize: 11 }} width={32} />
            <Tooltip
              labelFormatter={(v) => new Date(v + 'T12:00:00').toLocaleDateString('es-ES', { weekday: 'short', day: '2-digit', month: 'short', year: 'numeric' })}
              formatter={([value]) => [`${value} mensajes`, 'Total']}
            />
            <Area
              type="monotone"
              dataKey="count"
              stroke="#1976d2"
              strokeWidth={2}
              fill="url(#colorCount)"
            />
            <Brush
              dataKey="date"
              height={28}
              stroke="#1976d2"
              tickFormatter={(v) => new Date(v + 'T12:00:00').toLocaleDateString('es-ES', { month: 'short', year: '2-digit' })}
              onChange={handleBrushChange}
            />
          </AreaChart>
        </ResponsiveContainer>
      </Box>
    </Paper>
  );
};

export default MessagesOverTimeChart;
