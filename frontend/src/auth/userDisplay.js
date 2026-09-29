/**
 * Helpers de presentación del usuario (nombre, avatar, plan).
 * Preparado para ampliar cuando el backend exponga plan/avatar personalizados.
 */

export function getDisplayName(user) {
  if (!user) return '';
  const name = (user.name || '').trim();
  if (name && !name.includes('@')) return name;
  const email = (user.email || '').trim();
  if (email.includes('@')) return email.split('@')[0];
  return name || email || 'Usuario';
}

export function getInitials(user) {
  const label = getDisplayName(user);
  if (!label) return '?';
  const parts = label.replace(/[._-]+/g, ' ').split(/\s+/).filter(Boolean);
  if (parts.length >= 2) {
    return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
  }
  return label.slice(0, 2).toUpperCase();
}

/**
 * Plan visible en UI. Hoy se deriva del rol; más adelante vendrá del API.
 * - admin → Member
 * - resto → Free
 */
export function getPlanLabel(user) {
  if (!user) return 'Free';
  if (user.plan) return user.plan;
  if (user.role === 'admin') return 'Member';
  return 'Free';
}

export function getAvatarUrl(user) {
  return user?.avatar_url || user?.picture || null;
}
