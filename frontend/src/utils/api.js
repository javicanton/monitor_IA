import axios from 'axios';
import config from '../config';

// Configuración base de la API
const API_BASE_URL = config.API_BASE_URL;

// Crear instancia de axios con configuración base
const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000, // 30 segundos
  headers: {
    'Content-Type': 'application/json',
  },
});

// Interceptor para agregar token de autenticación
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token');
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
      // Token expirado o inválido
      localStorage.removeItem('access_token');
      localStorage.removeItem('user');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// Funciones de API para mensajes
export const messagesAPI = {
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
};

// Funciones de API para canales
export const channelsAPI = {
  // Obtener lista de canales
  getChannels: async () => {
    try {
      // Como no hay endpoint específico para canales, usamos el endpoint de filtros
      // para obtener los canales disponibles
      const response = await api.post('/filter_messages', { page: 1, per_page: 1 });
      if (response.data.success) {
        // Extraer canales del primer mensaje o usar datos de sesión
        return [];
      }
      return [];
    } catch (error) {
      console.error('Error al obtener canales:', error);
      return [];
    }
  },
};

// Funciones de API para autenticación
export const authAPI = {
  // Login
  login: async (credentials) => {
    try {
      const response = await api.post('/auth/login', credentials);
      return response.data;
    } catch (error) {
      console.error('Error en login:', error);
      throw error;
    }
  },

  // Registro
  register: async (userData) => {
    try {
      const response = await api.post('/auth/register', userData);
      return response.data;
    } catch (error) {
      console.error('Error en registro:', error);
      throw error;
    }
  },

  // Verificar token
  verifyToken: async () => {
    try {
      const response = await api.get('/auth/verify');
      return response.data;
    } catch (error) {
      console.error('Error al verificar token:', error);
      throw error;
    }
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
