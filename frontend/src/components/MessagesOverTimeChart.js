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
import { Box, Paper, Typography, CircularProgress, Alert, TextField, Button } from '@mui/material';
import { messagesAPI } from '../utils/api';

function formatDateLabel(ymd) {
  if (!ymd) return '';
  const d = new Date(ymd + 'T12:00:00');
  return d.toLocaleDateString('es-ES', { day: '2-digit', month: 'long', year: 'numeric' });
}

/**
 * Gráfico de evolución del número de mensajes por día.
 * Permite seleccionar un rango (brush) o una fecha concreta (campo "Ver solo esta fecha").
 */
const MessagesOverTimeChart = ({ onDateRangeChange, selectedDateStart, selectedDateEnd }) => {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [singleDateInput, setSingleDateInput] = useState('');
  useEffect(() => {
    if (!selectedDateStart && !selectedDateEnd) setSingleDateInput('');
    else if (selectedDateStart && selectedDateStart === selectedDateEnd) setSingleDateInput(selectedDateStart);
  }, [selectedDateStart, selectedDateEnd]);

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

  const handleBrushChange = (rangeOrStart, endIndexArg) => {
    if (!data.length || typeof onDateRangeChange !== 'function') return;
    let startIndex, endIndex;
    if (endIndexArg !== undefined && typeof rangeOrStart === 'number') {
      startIndex = rangeOrStart;
      endIndex = endIndexArg;
    } else if (typeof rangeOrStart === 'object' && rangeOrStart !== null && !Array.isArray(rangeOrStart)) {
      startIndex = rangeOrStart.startIndex;
      endIndex = rangeOrStart.endIndex;
    } else if (Array.isArray(rangeOrStart) && rangeOrStart.length >= 2) {
      startIndex = rangeOrStart[0];
      endIndex = rangeOrStart[1];
    } else {
      return;
    }
    if (startIndex == null || endIndex == null) return;
    const lastIdx = data.length - 1;
    const isFullRange = startIndex <= 0 && endIndex >= lastIdx;
    if (isFullRange) {
      try {
        onDateRangeChange('', '');
      } catch (e) {
        console.error('MessagesOverTimeChart onDateRangeChange:', e);
      }
      return;
    }
    const start = data[Math.min(Math.max(0, startIndex), lastIdx)]?.date;
    const end = data[Math.min(Math.max(0, endIndex), lastIdx)]?.date;
    if (start && end) {
      try {
        onDateRangeChange(start, end);
      } catch (e) {
        console.error('MessagesOverTimeChart onDateRangeChange:', e);
      }
    }
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

  const start = selectedDateStart || '';
  const end = selectedDateEnd || '';
  const hasRange = start && end;
  let countInRange = 0;
  if (hasRange && data.length) {
    const inRange = data.filter((d) => d.date >= start && d.date <= end);
    countInRange = inRange.reduce((acc, d) => acc + (d.count || 0), 0);
  }
  const titleText = hasRange
    ? `${countInRange.toLocaleString('es-ES')} mensajes disponibles publicados entre ${formatDateLabel(start)} y ${formatDateLabel(end)}`
    : 'Evolución de mensajes — selecciona un rango en el gráfico o elige una fecha concreta';

  const handleSingleDateChange = (e) => {
    const v = e.target.value;
    setSingleDateInput(v);
    if (v) onDateRangeChange(v, v);
  };
  const handleClearSingleDate = () => {
    setSingleDateInput('');
    onDateRangeChange('', '');
  };

  return (
    <Paper sx={{ p: 2, mb: 3 }} elevation={0} variant="outlined">
      <Typography variant="subtitle1" color="textSecondary" gutterBottom>
        {titleText}
      </Typography>
      <Box display="flex" flexWrap="wrap" alignItems="center" gap={2} sx={{ mb: 2 }}>
        <TextField
          size="small"
          label="Ver solo esta fecha"
          type="date"
          value={singleDateInput}
          onChange={handleSingleDateChange}
          InputLabelProps={{ shrink: true }}
          sx={{ width: 200 }}
        />
        {(singleDateInput || hasRange) && (
          <Button size="small" onClick={handleClearSingleDate}>
            Limpiar filtro de fecha
          </Button>
        )}
      </Box>
      <Box sx={{ width: '100%', minWidth: 0, height: 280, minHeight: 280 }}>
        <ResponsiveContainer width="100%" height={280} minWidth={0} minHeight={280}>
          <AreaChart
            data={data}
            margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
          >
            <defs>
              <linearGradient id="messagesOverTimeGradient" x1="0" y1="0" x2="0" y2="1">
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
              labelFormatter={(v) => (v ? new Date(v + 'T12:00:00').toLocaleDateString('es-ES', { weekday: 'short', day: '2-digit', month: 'short', year: 'numeric' }) : '')}
              formatter={(val) => {
                const n = Array.isArray(val) ? val[0] : val;
                return [`${Number(n) ?? 0} mensajes`, 'Total'];
              }}
            />
            <Area
              type="monotone"
              dataKey="count"
              stroke="#1976d2"
              strokeWidth={2}
              fill="url(#messagesOverTimeGradient)"
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
