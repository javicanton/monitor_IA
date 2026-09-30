import React, { useState } from 'react';
import {
  Avatar,
  Box,
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
import { useAuth } from '../AuthContext';
import {
  getAvatarUrl,
  getDisplayName,
  getInitials,
  getPlanLabel,
} from '../userDisplay';

const UserMenu = ({ onLogout }) => {
  const { user } = useAuth();
  const [anchorEl, setAnchorEl] = useState(null);
  const open = Boolean(anchorEl);

  if (!user) return null;

  const displayName = getDisplayName(user);
  const plan = getPlanLabel(user);
  const avatarUrl = getAvatarUrl(user);
  const initials = getInitials(user);

  const handleOpen = (event) => setAnchorEl(event.currentTarget);
  const handleClose = () => setAnchorEl(null);

  const handleLogout = async () => {
    handleClose();
    if (onLogout) await onLogout();
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
        <Typography variant="body2" noWrap sx={{ fontWeight: 600, lineHeight: 1.2 }}>
          {displayName}
        </Typography>
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
          paper: { sx: { minWidth: 220, mt: 1 } },
        }}
      >
        <Box sx={{ px: 2, py: 1.25 }}>
          <Typography variant="subtitle2">{displayName}</Typography>
          <Typography variant="caption" color="text.secondary" display="block">
            {user.email}
          </Typography>
          <Typography variant="caption" color="primary" display="block" sx={{ mt: 0.5 }}>
            Plan {plan}
          </Typography>
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
