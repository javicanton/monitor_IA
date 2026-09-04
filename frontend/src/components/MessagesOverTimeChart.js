import React, { useState, useEffect, useMemo, useRef, useCallback, forwardRef } from 'react';
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
import DatePicker, { registerLocale } from 'react-datepicker';
import { es } from 'date-fns/locale';
import { messagesAPI } from '../utils/api';
import 'react-datepicker/dist/react-datepicker.css';

registerLocale('es', es);

const BRUSH_COMMIT_MS = 180;

function formatDateLabel(ymd) {
  if (!ymd) return '';
  const d = new Date(ymd + 'T12:00:00');
  return d.toLocaleDateString('es-ES', { day: '2-digit', month: 'long', year: 'numeric' });
}

function toYmd(date) {
  if (!date) return '';
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

function parseYmd(ymd) {
  if (!ymd || typeof ymd !== 'string') return null;
  const [y, m, d] = ymd.split('-').map(Number);
  if (!y || !m || !d) return null;
  return new Date(y, m - 1, d);
}

const PRESET_RANGES = [
  { key: 'week', label: 'Última semana', days: 7 },
  { key: 'month', label: 'Último mes', days: 30 },
  { key: 'year', label: 'Último año', days: 365 },
];

function rangeForPreset(days) {
  const end = new Date();
  const start = new Date();
  start.setDate(end.getDate() - (days - 1));
  return { start: toYmd(start), end: toYmd(end) };
}

/** Filtros para la serie (sin fecha: el gráfico debe mostrar todo el histórico para poder cepillar). */
function filtersForSeries(filters) {
  if (!filters || typeof filters !== 'object') return {};
  const { dateStart, dateEnd, ...rest } = filters;
  return rest;
}

function brushIndexesFromDates(data, start, end) {
  if (!data.length) return { startIndex: 0, endIndex: 0 };
  const lastIdx = data.length - 1;
  if (!start && !end) return { startIndex: 0, endIndex: lastIdx };
  let startIndex = 0;
  let endIndex = lastIdx;
  if (start) {
    const found = data.findIndex((d) => d.date >= start);
    startIndex = found < 0 ? 0 : found;
  }
  if (end) {
    for (let i = lastIdx; i >= 0; i -= 1) {
      if (data[i].date <= end) {
        endIndex = i;
        break;
      }
    }
  }
  if (startIndex > endIndex) {
    const tmp = startIndex;
    startIndex = endIndex;
    endIndex = tmp;
  }
  return { startIndex, endIndex };
}

function parseBrushIndexes(rangeOrStart, endIndexArg) {
  if (endIndexArg !== undefined && typeof rangeOrStart === 'number') {
    return { startIndex: rangeOrStart, endIndex: endIndexArg };
  }
  if (typeof rangeOrStart === 'object' && rangeOrStart !== null && !Array.isArray(rangeOrStart)) {
    return { startIndex: rangeOrStart.startIndex, endIndex: rangeOrStart.endIndex };
  }
  if (Array.isArray(rangeOrStart) && rangeOrStart.length >= 2) {
    return { startIndex: rangeOrStart[0], endIndex: rangeOrStart[1] };
  }
  return null;
}

const DateRangeInput = forwardRef(function DateRangeInput(
  { value, onClick, onChange, onFocus, onBlur, onKeyDown, className, ...rest },
  ref
) {
  return (
    <TextField
      {...rest}
      size="small"
      label="Rango de fechas"
      placeholder="Elige inicio y fin"
      value={value || ''}
      onClick={onClick}
      onChange={onChange}
      onFocus={onFocus}
      onBlur={onBlur}
      onKeyDown={onKeyDown}
      inputRef={ref}
      className={className}
      InputLabelProps={{ shrink: true }}
      sx={{ minWidth: 260 }}
      autoComplete="off"
    />
  );
});

/**
 * Gráfico de evolución del número de mensajes por día.
 * Respeta filtros del menú (canal, temas, tipo de contenido). El rango de fechas
 * se aplica al soltar el brush o al elegir inicio y fin en el calendario.
 */
const MessagesOverTimeChart = ({ filters = {}, onDateRangeChange, selectedDateStart, selectedDateEnd }) => {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [rangeStart, setRangeStart] = useState(null);
  const [rangeEnd, setRangeEnd] = useState(null);
  const [calendarOpen, setCalendarOpen] = useState(false);

  const seriesKey = useMemo(() => JSON.stringify(filtersForSeries(filters)), [filters]);
  const filtersRef = useRef(filters);
  filtersRef.current = filters;

  const skipBrushRef = useRef(true);
  const pendingBrushRef = useRef(null);
  const brushTimerRef = useRef(null);
  const draggingBrushRef = useRef(false);
  const [brushKey, setBrushKey] = useState(0);
  const [brushIndexes, setBrushIndexes] = useState({ startIndex: 0, endIndex: 0 });
  const selectedRef = useRef({ start: selectedDateStart || '', end: selectedDateEnd || '' });
  selectedRef.current = { start: selectedDateStart || '', end: selectedDateEnd || '' };

  useEffect(() => {
    setRangeStart(parseYmd(selectedDateStart));
    setRangeEnd(parseYmd(selectedDateEnd));
  }, [selectedDateStart, selectedDateEnd]);

  useEffect(() => {
    if (draggingBrushRef.current) return;
    setBrushIndexes(brushIndexesFromDates(data, selectedDateStart, selectedDateEnd));
  }, [data, selectedDateStart, selectedDateEnd]);

  useEffect(() => {
    let cancelled = false;
    const fetchData = async () => {
      try {
        setLoading(true);
        setError(null);
        const res = await messagesAPI.getMessagesOverTime(filtersForSeries(filtersRef.current));
        if (!cancelled && res.success && Array.isArray(res.data)) {
          skipBrushRef.current = true;
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
  }, [seriesKey]);

  const emitRange = useCallback((start, end) => {
    if (typeof onDateRangeChange !== 'function') return;
    const nextStart = start || '';
    const nextEnd = end || '';
    const prev = selectedRef.current;
    if (nextStart === (prev.start || '') && nextEnd === (prev.end || '')) return;
    try {
      onDateRangeChange(nextStart, nextEnd);
    } catch (e) {
      console.error('MessagesOverTimeChart onDateRangeChange:', e);
    }
  }, [onDateRangeChange]);

  const applyDateRange = useCallback((start, end) => {
    if (!start && !end) {
      emitRange('', '');
      return;
    }
    if (start && end && start > end) {
      const tmp = start;
      start = end;
      end = tmp;
    }
    emitRange(start || '', end || '');
  }, [emitRange]);

  const commitBrush = useCallback(() => {
    if (brushTimerRef.current) {
      clearTimeout(brushTimerRef.current);
      brushTimerRef.current = null;
    }
    const pending = pendingBrushRef.current;
    pendingBrushRef.current = null;
    draggingBrushRef.current = false;
    if (!pending) return;
    applyDateRange(pending.start, pending.end);
  }, [applyDateRange]);

  useEffect(() => {
    const onPointerUp = () => {
      if (pendingBrushRef.current) commitBrush();
    };
    window.addEventListener('mouseup', onPointerUp);
    window.addEventListener('touchend', onPointerUp);
    return () => {
      window.removeEventListener('mouseup', onPointerUp);
      window.removeEventListener('touchend', onPointerUp);
      if (brushTimerRef.current) clearTimeout(brushTimerRef.current);
    };
  }, [commitBrush]);

  const handleBrushChange = (rangeOrStart, endIndexArg) => {
    if (!data.length) return;
    if (skipBrushRef.current) {
      skipBrushRef.current = false;
      return;
    }
    const indexes = parseBrushIndexes(rangeOrStart, endIndexArg);
    if (!indexes || indexes.startIndex == null || indexes.endIndex == null) return;
    const lastIdx = data.length - 1;
    const startIndex = Math.min(Math.max(0, indexes.startIndex), lastIdx);
    const endIndex = Math.min(Math.max(0, indexes.endIndex), lastIdx);
    draggingBrushRef.current = true;
    setBrushIndexes({ startIndex, endIndex });
    const isFullRange = startIndex <= 0 && endIndex >= lastIdx;
    pendingBrushRef.current = isFullRange
      ? { start: '', end: '' }
      : { start: data[startIndex]?.date || '', end: data[endIndex]?.date || '' };
    if (brushTimerRef.current) clearTimeout(brushTimerRef.current);
    brushTimerRef.current = setTimeout(commitBrush, BRUSH_COMMIT_MS);
  };

  const handleCalendarChange = (dates) => {
    const [start, end] = Array.isArray(dates) ? dates : [dates, null];
    setRangeStart(start || null);
    setRangeEnd(end || null);
    if (start && end) {
      applyDateRange(toYmd(start), toYmd(end));
      setCalendarOpen(false);
    }
  };

  const handleClearDateRange = () => {
    draggingBrushRef.current = false;
    pendingBrushRef.current = null;
    if (brushTimerRef.current) {
      clearTimeout(brushTimerRef.current);
      brushTimerRef.current = null;
    }
    skipBrushRef.current = true;
    setRangeStart(null);
    setRangeEnd(null);
    setCalendarOpen(false);
    setBrushIndexes(brushIndexesFromDates(data, '', ''));
    setBrushKey((key) => key + 1);
    applyDateRange('', '');
  };

  const handlePresetRange = (days) => {
    const { start, end } = rangeForPreset(days);
    setRangeStart(parseYmd(start));
    setRangeEnd(parseYmd(end));
    setCalendarOpen(false);
    applyDateRange(start, end);
  };

  const handleDayClick = (point) => {
    if (point?.date) {
      setRangeStart(parseYmd(point.date));
      setRangeEnd(parseYmd(point.date));
      applyDateRange(point.date, point.date);
    }
  };

  const renderActiveDot = (props) => {
    const { cx, cy, payload } = props;
    if (cx == null || cy == null) return null;
    return (
      <g
        onClick={(e) => { e.stopPropagation(); handleDayClick(payload); }}
        style={{ cursor: 'pointer' }}
        role="button"
        aria-label={`Seleccionar día ${payload?.date || ''}`}
      >
        <circle cx={cx} cy={cy} r={4} fill="#1976d2" stroke="#fff" strokeWidth={2} />
      </g>
    );
  };

  if (loading && !data.length) {
    return (
      <Paper sx={{ p: 2, mb: 3, minHeight: 280, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
        <CircularProgress />
        <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
          Cargando gráfico de evolución…
        </Typography>
      </Paper>
    );
  }

  if (error && !data.length) {
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
  const hasRange = Boolean(start && end);
  const countInRange = hasRange
    ? data.filter((d) => d.date >= start && d.date <= end).reduce((acc, d) => acc + (d.count || 0), 0)
    : 0;
  const titleText = hasRange
    ? `${countInRange.toLocaleString('es-ES')} mensajes entre ${formatDateLabel(start)} y ${formatDateLabel(end)}`
    : 'Evolución de mensajes — selecciona un rango en el gráfico o indica fecha inicio y fin';

  const activePresetKey = PRESET_RANGES.find(({ days }) => {
    const preset = rangeForPreset(days);
    return preset.start === start && preset.end === end;
  })?.key;

  const hasDateSelection = Boolean(rangeStart || rangeEnd || hasRange);

  return (
    <Paper sx={{ p: 2, mb: 3, position: 'relative' }} elevation={0} variant="outlined">
      {loading && (
        <Box
          sx={{
            position: 'absolute',
            inset: 0,
            zIndex: 2,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            bgcolor: 'rgba(255,255,255,0.55)',
            pointerEvents: 'none',
          }}
        >
          <CircularProgress size={28} />
        </Box>
      )}
      <Typography variant="subtitle1" color="textSecondary" gutterBottom>
        {titleText}
      </Typography>
      <Box display="flex" flexWrap="wrap" alignItems="center" gap={2} sx={{ mb: 2 }}>
        <DatePicker
          selectsRange
          startDate={rangeStart}
          endDate={rangeEnd}
          selected={rangeStart}
          onChange={handleCalendarChange}
          locale={es}
          dateFormat="dd/MM/yyyy"
          monthsShown={2}
          shouldCloseOnSelect={false}
          allowSameDay
          showIcon={false}
          preventOpenOnFocus
          open={calendarOpen}
          onInputClick={() => setCalendarOpen(true)}
          onClickOutside={() => setCalendarOpen(false)}
          onCalendarClose={() => setCalendarOpen(false)}
          customInput={<DateRangeInput />}
          placeholderText="Elige inicio y fin"
          popperClassName="monitoria-date-range-popper"
          calendarClassName="monitoria-date-range"
          popperPlacement="bottom-start"
          maxDate={new Date()}
        />
        <Box display="flex" flexWrap="wrap" gap={1} alignItems="center">
          {PRESET_RANGES.map(({ key, label, days }) => (
            <Button
              key={key}
              size="small"
              variant={activePresetKey === key ? 'contained' : 'outlined'}
              onClick={() => handlePresetRange(days)}
            >
              {label}
            </Button>
          ))}
        </Box>
        {hasDateSelection && (
          <Button size="small" onClick={handleClearDateRange}>
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
              isAnimationActive={false}
              dot={false}
              activeDot={renderActiveDot}
            />
            <Brush
              key={brushKey}
              dataKey="date"
              height={28}
              stroke="#1976d2"
              startIndex={brushIndexes.startIndex}
              endIndex={brushIndexes.endIndex}
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
