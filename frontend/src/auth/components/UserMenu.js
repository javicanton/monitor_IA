import React, { useState } from 'react';
import {
  Avatar,
  Box,
  Chip,
  CircularProgress,
  Divider,
  IconButton,
  ListItemIcon,
  ListItemText,
  Menu,
  MenuItem,
  Typography,
} from '@mui/material';
import LogoutIcon from '@mui/icons-material/Logout';
import SettingsOutlinedIcon from '@mui/icons-material/SettingsOutlined';
import DownloadIcon from '@mui/icons-material/Download';
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
  const [anchorEl, setAnchorEl] = useState(null);
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState('');
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
          paper: { sx: { minWidth: 240, mt: 1 } },
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
    </Box>
  );
};

export default UserMenu;
