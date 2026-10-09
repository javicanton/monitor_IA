import axios from 'axios';
import config from '../config';

// Configuración base de la API
const API_BASE_URL = config.API_BASE_URL;

// Crear instancia de axios con configuración base
const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 90000, // 90 segundos (carga de mensajes con filtros puede ser pesada)
  headers: {
    'Content-Type': 'application/json',
  },
});

// Interceptor para agregar token de autenticación
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Interceptor para manejar respuestas de error
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      if (!window.location.pathname.startsWith('/login')
          && !window.location.pathname.startsWith('/auth/verify')) {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

// Funciones de API para mensajes
export const messagesAPI = {
  // Evolución de mensajes por día (canal, temas, etc.; sin fecha para no recortar el brush)
  getMessagesOverTime: async (filters = {}) => {
    try {
      const { dateStart, dateEnd, ...rest } = filters || {};
      const body = Object.keys(rest).length ? rest : {};
      const response = Object.keys(body).length
        ? await api.post('/messages_over_time', body)
        : await api.get('/messages_over_time');
      return response.data;
    } catch (error) {
      console.error('Error al obtener evolución de mensajes:', error);
      throw error;
    }
  },

  // Obtener mensajes con filtros
  getMessages: async (filters = {}) => {
    try {
      const response = await api.post('/filter_messages', filters);
      return response.data;
    } catch (error) {
      console.error('Error al obtener mensajes:', error);
      throw error;
    }
  },

  // Cargar más mensajes
  loadMore: async (offset, filters = {}) => {
    try {
      const params = new URLSearchParams({ offset, ...filters });
      const response = await api.get(`/load_more/${offset}?${params}`);
      return response.data;
    } catch (error) {
      console.error('Error al cargar más mensajes:', error);
      throw error;
    }
  },

  // Etiquetar mensaje
  labelMessage: async (messageId, label) => {
    try {
      const response = await api.post('/label', { message_id: messageId, label });
      return response.data;
    } catch (error) {
      console.error('Error al etiquetar mensaje:', error);
      throw error;
    }
  },

  // Exportar mensajes relevantes
  exportRelevants: async () => {
    try {
      const response = await api.get('/export_relevants');
      return response.data;
    } catch (error) {
      console.error('Error al exportar mensajes relevantes:', error);
      throw error;
    }
  },

  // Descargar mensajes filtrados como CSV
  downloadFilteredCSV: async (filters = {}) => {
    try {
      const response = await api.post('/download_filtered_messages', filters, {
        responseType: 'blob',
      });
      return response;
    } catch (error) {
      console.error('Error al descargar mensajes:', error);
      throw error;
    }
  },

  // Frescura de datos (min/max fecha en BD)
  getDataStatus: async () => {
    try {
      const response = await api.get('/api/data_status');
      return response.data;
    } catch (error) {
      console.error('Error al obtener estado de datos:', error);
      throw error;
    }
  },
};

// Funciones de API para canales
export const channelsAPI = {
  // Obtener lista de canales
  getChannels: async () => {
    try {
      const response = await api.get('/channels');
      if (response.data.success) {
        return response.data.channels || [];
      }
      return [];
    } catch (error) {
      console.error('Error al obtener canales:', error);
      return [];
    }
  },

  // Proponer un canal para monitorizaci?n (sin login)
  suggestChannel: async ({ username, note, email }) => {
    try {
      const response = await api.post('/api/channels/suggest', {
        username,
        note,
        email,
      });
      return response.data;
    } catch (error) {
      console.error('Error al proponer canal:', error);
      throw error;
    }
  },

  // Descargar grafo de canales (ZIP con nodos y aristas)
  downloadChannelGraph: async () => {
    try {
      const response = await api.get('/download_channel_graph', {
        responseType: 'blob',
      });
      return response;
    } catch (error) {
      console.error('Error al descargar canales:', error);
      throw error;
    }
  },

  // Grafo interactivo (nodos + aristas)
  getGraph: async ({ min_forwards = 1, include_discontinued = true } = {}) => {
    const params = {
      min_forwards,
      include_discontinued: include_discontinued ? '1' : '0',
    };
    const response = await api.get('/api/channels/graph', { params });
    if (!response.data?.success) {
      throw new Error(response.data?.error || 'No se pudo cargar el grafo');
    }
    return response.data;
  },

  // Estadísticas de un canal
  getChannelStats: async (username, { days = 30 } = {}) => {
    const params = {
      days: days == null ? 'all' : days,
    };
    const response = await api.get(
      `/api/channels/${encodeURIComponent(username)}/stats`,
      { params }
    );
    if (!response.data?.success) {
      throw new Error(response.data?.error || 'No se pudieron cargar las estadísticas');
    }
    return response.data;
  },

  // Admin: alta inmediata. Usuario: propuesta por email.
  monitorChannel: async ({ username, title, note, email } = {}) => {
    const response = await api.post('/api/channels/monitor', {
      username,
      title,
      note,
      email,
    });
    if (!response.data?.success) {
      throw new Error(response.data?.error || 'No se pudo incluir el canal');
    }
    return response.data;
  },
};

// Funciones de API para topics
export const topicsAPI = {
  // Obtener lista de topics
  getTopics: async () => {
    try {
      const response = await api.get('/topics');
      if (response.data.success) {
        return response.data.topics || [];
      }
      return [];
    } catch (error) {
      console.error('Error al obtener topics:', error);
      return [];
    }
  },
};

// Funciones de API para autenticación
export const authAPI = {
  requestMagicLink: async (email) => {
    const response = await api.post('/auth/login-request', { email });
    return response.data;
  },

  verifyMagicLink: async (payload) => {
    const body = typeof payload === 'string' ? { token: payload } : (payload || {});
    const response = await api.post('/auth/verify-magic-link', body);
    return response.data;
  },

  me: async () => {
    const response = await api.get('/auth/me');
    return response.data;
  },

  logout: async () => {
    const response = await api.post('/auth/logout');
    return response.data;
  },

  /** Descarga CSV de actividad (solo admin). Dispara descarga en el navegador. */
  downloadActivityCsv: async (days = 7) => {
    const response = await api.get('/auth/admin/activity/export', {
      params: { days },
      responseType: 'blob',
    });
    const disposition = response.headers['content-disposition'] || '';
    const match = /filename="?([^"]+)"?/i.exec(disposition);
    const filename = match?.[1] || `user_activity_last_${days}d.csv`;
    const url = window.URL.createObjectURL(new Blob([response.data], { type: 'text/csv' }));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', filename);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
    return true;
  },

  /**
   * Invita usuario (solo admin): añade a allowlist, genera magic link
   * y opcionalmente envía el correo. Siempre devuelve magic_link.
   */
  inviteUser: async ({ email, role = 'user', sendEmail = true }) => {
    const response = await api.post('/auth/admin/invite', {
      email,
      role,
      send_email: sendEmail,
    });
    return response.data;
  },
};

// Función para verificar el estado de la conexión
export const checkConnection = async () => {
  try {
    const response = await api.get('/');
    return response.status === 200;
  } catch (error) {
    console.error('Error al verificar conexión:', error);
    return false;
  }
};

export default api;
