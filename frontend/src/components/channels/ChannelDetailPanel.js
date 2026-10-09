import React from 'react';
import {
  Box,
  Button,
  Chip,
  Divider,
  Link,
  List,
  ListItemButton,
  ListItemText,
  Stack,
  Typography,
  CircularProgress,
} from '@mui/material';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import ArticleIcon from '@mui/icons-material/Article';

const formatNum = (value, digits = 0) => {
  const n = Number(value);
  if (!Number.isFinite(n)) return '—';
  return new Intl.NumberFormat('es-ES', {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits > 0 ? Math.min(digits, 1) : 0,
  }).format(n);
};

const statusLabel = (channel) => {
  if (!channel) return '';
  if (channel.discontinued || channel.status === 'error') return 'Descontinuado / error';
  if (!channel.monitored) return 'Solo en grafo';
  if (channel.status === 'active') return 'Activo';
  return channel.status || 'Desconocido';
};

const statusColor = (channel) => {
  if (!channel) return 'default';
  if (channel.discontinued || channel.status === 'error') return 'error';
  if (!channel.monitored) return 'warning';
  if (channel.status === 'active') return 'success';
  return 'default';
};

function NeighborList({ title, items, onSelect }) {
  if (!items?.length) {
    return (
      <Box mb={2}>
        <Typography variant="subtitle2" gutterBottom>{title}</Typography>
        <Typography variant="body2" color="text.secondary">Sin conexiones</Typography>
      </Box>
    );
  }
  return (
    <Box mb={2}>
      <Typography variant="subtitle2" gutterBottom>{title}</Typography>
      <List dense disablePadding>
        {items.slice(0, 12).map((item) => (
          <ListItemButton
            key={item.username}
            onClick={() => onSelect && onSelect(item.username)}
            sx={{ borderRadius: 1, py: 0.25 }}
          >
            <ListItemText
              primary={`@${item.username}`}
              secondary={`${formatNum(item.forward_count)} reenvíos`}
              primaryTypographyProps={{ variant: 'body2' }}
              secondaryTypographyProps={{ variant: 'caption' }}
            />
          </ListItemButton>
        ))}
      </List>
    </Box>
  );
}

function ChannelDetailPanel({
  meta,
  selectedUsername,
  detail,
  loading,
  days,
  onDaysChange,
  onSelectNeighbor,
  onViewMessages,
}) {
  if (!selectedUsername) {
    return (
      <Box>
        <Typography variant="h6" gutterBottom>Red de canales</Typography>
        <Typography variant="body2" color="text.secondary" paragraph>
          Pulsa un nodo del grafo para ver su ficha y estadísticas.
        </Typography>
        {meta && (
          <Stack spacing={1.25}>
            <Typography variant="body2">
              <strong>{formatNum(meta.node_count)}</strong> nodos ·{' '}
              <strong>{formatNum(meta.edge_count)}</strong> aristas
            </Typography>
            <Typography variant="body2">
              Monitorizados activos: <strong>{formatNum(meta.active_count)}</strong>
            </Typography>
            {meta.top_emitters?.length > 0 && (
              <Box>
                <Typography variant="subtitle2">Top orígenes de reenvío</Typography>
                {meta.top_emitters.map((row) => (
                  <Typography key={row.username} variant="body2" color="text.secondary">
                    @{row.username} · {formatNum(row.forward_count)}
                  </Typography>
                ))}
              </Box>
            )}
            {meta.top_receivers?.length > 0 && (
              <Box>
                <Typography variant="subtitle2">Top receptores</Typography>
                {meta.top_receivers.map((row) => (
                  <Typography key={row.username} variant="body2" color="text.secondary">
                    @{row.username} · {formatNum(row.forward_count)}
                  </Typography>
                ))}
              </Box>
            )}
          </Stack>
        )}
      </Box>
    );
  }

  if (loading && !detail) {
    return (
      <Box display="flex" justifyContent="center" py={6}>
        <CircularProgress size={28} />
      </Box>
    );
  }

  if (!detail) {
    return (
      <Typography variant="body2" color="text.secondary">
        No se pudo cargar el canal @{selectedUsername}.
      </Typography>
    );
  }

  const { channel, stats, neighbors } = detail;

  return (
    <Box>
      <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" mb={1}>
        <Typography variant="h6" sx={{ mr: 0.5 }}>{channel.title}</Typography>
        <Chip size="small" label={statusLabel(channel)} color={statusColor(channel)} />
      </Stack>
      <Typography variant="body2" color="text.secondary" gutterBottom>
        @{channel.username}
      </Typography>

      <Stack direction="row" spacing={1} flexWrap="wrap" mb={2}>
        <Button
          size="small"
          variant="contained"
          startIcon={<ArticleIcon />}
          onClick={() => onViewMessages && onViewMessages(channel)}
        >
          Ver mensajes
        </Button>
        <Button
          size="small"
          variant="outlined"
          endIcon={<OpenInNewIcon />}
          component={Link}
          href={channel.telegram_url}
          target="_blank"
          rel="noopener noreferrer"
          underline="none"
        >
          Telegram
        </Button>
      </Stack>

      <Stack direction="row" spacing={1} mb={2}>
        {[7, 30, 90].map((d) => (
          <Chip
            key={d}
            size="small"
            label={`${d}d`}
            color={days === d ? 'primary' : 'default'}
            variant={days === d ? 'filled' : 'outlined'}
            onClick={() => onDaysChange && onDaysChange(d)}
          />
        ))}
        <Chip
          size="small"
          label="Todo"
          color={days == null ? 'primary' : 'default'}
          variant={days == null ? 'filled' : 'outlined'}
          onClick={() => onDaysChange && onDaysChange(null)}
        />
      </Stack>

      {loading && (
        <Box mb={1}><CircularProgress size={16} /></Box>
      )}

      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: 1.25,
          mb: 2,
        }}
      >
        <Stat label="Mensajes" value={formatNum(stats.message_count)} />
        <Stat label="Posts / día" value={formatNum(stats.posts_per_day, 2)} />
        <Stat label="Views media" value={formatNum(stats.avg_views, 0)} />
        <Stat label="Reenvíos media" value={formatNum(stats.avg_forwards, 1)} />
        <Stat label="Respuestas media" value={formatNum(stats.avg_replies, 1)} />
        <Stat label="Score medio" value={formatNum(stats.avg_score, 2)} />
        <Stat label="Suscriptores" value="N/D" />
        <Stat label="Días con pubs." value={formatNum(stats.active_days)} />
      </Box>

      <Typography variant="caption" color="text.secondary" display="block" mb={1}>
        Rango en dataset:{' '}
        {stats.first_message_at ? new Date(stats.first_message_at).toLocaleDateString('es-ES') : '—'}
        {' → '}
        {stats.last_message_at ? new Date(stats.last_message_at).toLocaleDateString('es-ES') : '—'}
      </Typography>

      {(channel.source || channel.last_scraped_at) && (
        <Typography variant="caption" color="text.secondary" display="block" mb={2}>
          {channel.source ? `Origen: ${channel.source}` : ''}
          {channel.last_scraped_at
            ? ` · Último scrape: ${new Date(channel.last_scraped_at).toLocaleString('es-ES')}`
            : ''}
        </Typography>
      )}

      {channel.last_error && (
        <Typography variant="caption" color="error" display="block" mb={2}>
          Error: {channel.last_error}
        </Typography>
      )}

      <Divider sx={{ my: 1.5 }} />
      <NeighborList
        title="Reenvía desde (entrantes)"
        items={neighbors?.inbound}
        onSelect={onSelectNeighbor}
      />
      <NeighborList
        title="Es reenviado en (salientes)"
        items={neighbors?.outbound}
        onSelect={onSelectNeighbor}
      />
    </Box>
  );
}

function Stat({ label, value }) {
  return (
    <Box sx={{ bgcolor: 'grey.50', borderRadius: 1, px: 1.25, py: 1 }}>
      <Typography variant="caption" color="text.secondary" display="block">{label}</Typography>
      <Typography variant="subtitle1" sx={{ fontWeight: 600, lineHeight: 1.2 }}>{value}</Typography>
    </Box>
  );
}

export default ChannelDetailPanel;
