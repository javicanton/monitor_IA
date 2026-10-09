import React, { useState } from 'react';
import {
  Alert,
  Avatar,
  Box,
  Button,
  Checkbox,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  FormControlLabel,
  IconButton,
  ListItemIcon,
  ListItemText,
  Menu,
  MenuItem,
  TextField,
  Typography,
} from '@mui/material';
import LogoutIcon from '@mui/icons-material/Logout';
import SettingsOutlinedIcon from '@mui/icons-material/SettingsOutlined';
import DownloadIcon from '@mui/icons-material/Download';
import PersonAddAltIcon from '@mui/icons-material/PersonAddAlt';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import HubOutlinedIcon from '@mui/icons-material/HubOutlined';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../AuthContext';
import {
  getAvatarUrl,
  getDisplayName,
  getInitials,
  getPlanLabel,
} from '../userDisplay';
import { authAPI } from '../../utils/api';

const UserMenu = ({ onLogout }) => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [anchorEl, setAnchorEl] = useState(null);
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState('');
  const [inviteOpen, setInviteOpen] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteSendEmail, setInviteSendEmail] = useState(true);
  const [inviteLoading, setInviteLoading] = useState(false);
  const [inviteError, setInviteError] = useState('');
  const [inviteResult, setInviteResult] = useState(null);
  const [copied, setCopied] = useState(false);
  const open = Boolean(anchorEl);

  if (!user) return null;

  const displayName = getDisplayName(user);
  const plan = getPlanLabel(user);
  const avatarUrl = getAvatarUrl(user);
  const initials = getInitials(user);
  const isAdmin = user.role === 'admin';

  const handleOpen = (event) => {
    setDownloadError('');
    setAnchorEl(event.currentTarget);
  };
  const handleClose = () => setAnchorEl(null);

  const handleLogout = async () => {
    handleClose();
    if (onLogout) await onLogout();
  };

  const handleDownloadActivity = async () => {
    try {
      setDownloadError('');
      setDownloading(true);
      await authAPI.downloadActivityCsv(7);
    } catch (err) {
      const data = err.response?.data;
      let message = 'No se pudo descargar la actividad';
      if (data && typeof data === 'object' && !(data instanceof Blob) && data.error) {
        message = data.error;
      }
      setDownloadError(message);
    } finally {
      setDownloading(false);
    }
  };

  const openInviteDialog = () => {
    handleClose();
    setInviteEmail('');
    setInviteSendEmail(true);
    setInviteError('');
    setInviteResult(null);
    setCopied(false);
    setInviteOpen(true);
  };

  const closeInviteDialog = () => {
    if (inviteLoading) return;
    setInviteOpen(false);
  };

  const handleInvite = async (event) => {
    event.preventDefault();
    const email = inviteEmail.trim().toLowerCase();
    if (!email || !email.includes('@')) {
      setInviteError('Introduce un email válido');
      return;
    }
    try {
      setInviteLoading(true);
      setInviteError('');
      setInviteResult(null);
      setCopied(false);
      const result = await authAPI.inviteUser({
        email,
        role: 'user',
        sendEmail: inviteSendEmail,
      });
      setInviteResult(result);
    } catch (err) {
      setInviteError(err.response?.data?.error || 'No se pudo generar la invitación');
    } finally {
      setInviteLoading(false);
    }
  };

  const handleCopyLink = async () => {
    const text = inviteResult?.magic_link;
    if (!text) return;

    const copyWithFallback = () => {
      const el = document.createElement('textarea');
      el.value = text;
      el.setAttribute('readonly', '');
      el.style.position = 'fixed';
      el.style.top = '0';
      el.style.left = '0';
      el.style.width = '1px';
      el.style.height = '1px';
      el.style.padding = '0';
      el.style.border = 'none';
      el.style.outline = 'none';
      el.style.boxShadow = 'none';
      el.style.background = 'transparent';
      el.style.opacity = '0';
      document.body.appendChild(el);
      el.focus();
      el.select();
      el.setSelectionRange(0, text.length);
      let ok = false;
      try {
        ok = document.execCommand('copy');
      } catch {
        ok = false;
      }
      document.body.removeChild(el);
      return ok;
    };

    try {
      if (navigator.clipboard?.writeText && window.isSecureContext) {
        await navigator.clipboard.writeText(text);
        setInviteError('');
        setCopied(true);
        return;
      }
    } catch {
      // fallback below
    }

    if (copyWithFallback()) {
      setInviteError('');
      setCopied(true);
    } else {
      setInviteError('No se pudo copiar. Selecciona el enlace manualmente.');
    }
  };

  return (
    <Box
      sx={{
        position: 'fixed',
        top: 12,
        right: 12,
        zIndex: 1300,
        display: 'flex',
        alignItems: 'center',
        gap: 1,
        bgcolor: 'background.paper',
        pl: 1.25,
        pr: 0.5,
        py: 0.5,
        borderRadius: 2,
        boxShadow: 1,
      }}
    >
      <Box sx={{ display: { xs: 'none', sm: 'block' }, minWidth: 0, mr: 0.5 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
          <Typography variant="body2" noWrap sx={{ fontWeight: 600, lineHeight: 1.2 }}>
            {displayName}
          </Typography>
          {isAdmin && (
            <Chip
              label="Admin"
              size="small"
              color="secondary"
              sx={{ height: 20, fontSize: 11, fontWeight: 600 }}
            />
          )}
        </Box>
        <Typography variant="caption" color="text.secondary" sx={{ lineHeight: 1.2 }}>
          {plan}
        </Typography>
      </Box>

      <IconButton
        onClick={handleOpen}
        size="small"
        aria-label="Menú de usuario"
        aria-controls={open ? 'user-menu' : undefined}
        aria-haspopup="true"
        aria-expanded={open ? 'true' : undefined}
      >
        <Avatar
          src={avatarUrl || undefined}
          alt={displayName}
          sx={{ width: 36, height: 36, bgcolor: 'primary.main', fontSize: 14 }}
        >
          {!avatarUrl && initials}
        </Avatar>
      </IconButton>

      <Menu
        id="user-menu"
        anchorEl={anchorEl}
        open={open}
        onClose={handleClose}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
        transformOrigin={{ vertical: 'top', horizontal: 'right' }}
        slotProps={{
          paper: { sx: { minWidth: 260, mt: 1 } },
        }}
      >
        <Box sx={{ px: 2, py: 1.25 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.25 }}>
            <Typography variant="subtitle2">{displayName}</Typography>
            {isAdmin && (
              <Chip label="Admin" size="small" color="secondary" sx={{ height: 20, fontSize: 11 }} />
            )}
          </Box>
          <Typography variant="caption" color="text.secondary" display="block">
            {user.email}
          </Typography>
          <Typography variant="caption" color="primary" display="block" sx={{ mt: 0.5 }}>
            Plan {plan}
          </Typography>
          {downloadError && (
            <Typography variant="caption" color="error" display="block" sx={{ mt: 0.75 }}>
              {downloadError}
            </Typography>
          )}
        </Box>
        <Divider />
        <MenuItem
          onClick={() => {
            handleClose();
            navigate('/canales');
          }}
        >
          <ListItemIcon>
            <HubOutlinedIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText
            primary="Canales"
            secondary="Grafo y estadísticas"
            secondaryTypographyProps={{ variant: 'caption' }}
          />
        </MenuItem>
        <MenuItem disabled>
          <ListItemIcon>
            <SettingsOutlinedIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText
            primary="Preferencias"
            secondary="Próximamente"
            secondaryTypographyProps={{ variant: 'caption' }}
          />
        </MenuItem>
        {isAdmin && (
          <MenuItem onClick={openInviteDialog}>
            <ListItemIcon>
              <PersonAddAltIcon fontSize="small" />
            </ListItemIcon>
            <ListItemText
              primary="Invitar / generar enlace"
              secondary="Añade a allowlist y crea magic link"
              secondaryTypographyProps={{ variant: 'caption' }}
            />
          </MenuItem>
        )}
        {isAdmin && (
          <MenuItem onClick={handleDownloadActivity} disabled={downloading}>
            <ListItemIcon>
              {downloading ? (
                <CircularProgress size={18} />
              ) : (
                <DownloadIcon fontSize="small" />
              )}
            </ListItemIcon>
            <ListItemText
              primary="Descargar actividad (7 días)"
              secondary="CSV de uso de la herramienta"
              secondaryTypographyProps={{ variant: 'caption' }}
            />
          </MenuItem>
        )}
        <Divider />
        <MenuItem onClick={handleLogout}>
          <ListItemIcon>
            <LogoutIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText primary="Cerrar sesión" />
        </MenuItem>
      </Menu>

      <Dialog open={inviteOpen} onClose={closeInviteDialog} fullWidth maxWidth="sm">
        <DialogTitle>Invitar usuario</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Añade el email a la allowlist y genera un enlace de acceso (15 min, un solo uso).
            Si el correo no llega, copia el enlace y envíaselo tú.
          </Typography>
          <Box component="form" id="invite-form" onSubmit={handleInvite}>
            <TextField
              autoFocus
              fullWidth
              label="Email"
              type="email"
              value={inviteEmail}
              onChange={(e) => setInviteEmail(e.target.value)}
              disabled={inviteLoading || Boolean(inviteResult)}
              margin="dense"
              required
            />
            <FormControlLabel
              control={
                <Checkbox
                  checked={inviteSendEmail}
                  onChange={(e) => setInviteSendEmail(e.target.checked)}
                  disabled={inviteLoading || Boolean(inviteResult)}
                />
              }
              label="Enviar también por correo"
            />
          </Box>
          {inviteError && (
            <Alert severity="error" sx={{ mt: 1.5 }}>
              {inviteError}
            </Alert>
          )}
          {inviteResult && (
            <Box sx={{ mt: 2 }}>
              <Alert severity={inviteResult.email_sent ? 'success' : 'warning'} sx={{ mb: 1.5 }}>
                {inviteResult.message}
                {!inviteResult.email_sent && inviteResult.email_error
                  ? ` (${inviteResult.email_error})`
                  : ''}
              </Alert>
              <TextField
                fullWidth
                label="Magic link"
                value={inviteResult.magic_link || ''}
                InputProps={{ readOnly: true }}
                size="small"
                multiline
                minRows={2}
              />
              <Button
                startIcon={<ContentCopyIcon />}
                onClick={handleCopyLink}
                sx={{ mt: 1 }}
                size="small"
              >
                {copied ? 'Copiado' : 'Copiar enlace'}
              </Button>
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={closeInviteDialog} disabled={inviteLoading}>
            Cerrar
          </Button>
          {!inviteResult && (
            <Button
              type="submit"
              form="invite-form"
              variant="contained"
              disabled={inviteLoading}
              startIcon={inviteLoading ? <CircularProgress size={16} color="inherit" /> : null}
            >
              Generar enlace
            </Button>
          )}
          {inviteResult && (
            <Button
              onClick={() => {
                setInviteResult(null);
                setInviteError('');
                setCopied(false);
                setInviteEmail('');
              }}
            >
              Invitar otro
            </Button>
          )}
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default UserMenu;
