// Configuración del frontend
const defaultApiBaseUrl =
  process.env.REACT_APP_API_URL ||
  (typeof window !== 'undefined'
    ? `${window.location.protocol}//${window.location.hostname}:5001`
    : 'http://localhost:5001');

const config = {
  // URL de la API del backend
  API_BASE_URL: defaultApiBaseUrl,
  
  // Configuración de AWS S3
  S3_BUCKET: process.env.REACT_APP_S3_BUCKET || 'monitoria-data',
  AWS_REGION: process.env.REACT_APP_AWS_REGION || 'eu-north-1',
  
  // Configuración de la aplicación
  APP_NAME: 'Telegram Analytics App',
  APP_VERSION: '1.0.0',
  
  // Configuración de paginación
  MESSAGES_PER_PAGE: 24,
  MAX_MESSAGES_PER_PAGE: 100,
  
  // Configuración de timeouts
  API_TIMEOUT: 30000, // 30 segundos
  REFRESH_INTERVAL: 60000, // 1 minuto
  
  // Configuración de filtros por defecto
  DEFAULT_FILTERS: {
    dateStart: '',
    dateEnd: '',
    channel: '',
    scoreMin: '',
    scoreMax: '',
    mediaType: '',
    sortBy: 'score'
  },
  
  // Tipos de contenido soportados
  MEDIA_TYPES: [
    { value: 'text', label: 'Texto' },
    { value: 'photo', label: 'Foto' },
    { value: 'video', label: 'Video' },
    { value: 'link', label: 'Enlace' },
    { value: 'document', label: 'Documento' },
    { value: 'audio', label: 'Audio' },
    { value: 'sticker', label: 'Sticker' }
  ],
  
  // Opciones de ordenamiento
  SORT_OPTIONS: [
    { value: 'score', label: 'Puntuación (Score)' },
    { value: 'views', label: 'Número de vistas' },
    { value: 'date', label: 'Fecha' },
    { value: 'channel', label: 'Canal' }
  ],
  
  // Configuración de etiquetas
  LABELS: {
    RELEVANT: 1,
    NOT_RELEVANT: 0
  },
  
  // Mensajes de la aplicación
  MESSAGES: {
    LOADING: 'Cargando mensajes...',
    NO_MESSAGES: 'No se encontraron mensajes con los filtros aplicados',
    ERROR_LOADING: 'Error al cargar los mensajes',
    SUCCESS_LABEL: 'Mensaje etiquetado correctamente',
    ERROR_LABEL: 'Error al etiquetar el mensaje',
    SUCCESS_EXPORT: 'Mensajes relevantes exportados correctamente',
    ERROR_EXPORT: 'Error al exportar mensajes relevantes',
    CONNECTION_ERROR: 'Error de conexión con el servidor',
    S3_CONNECTION_INFO: 'Conectado a AWS S3: Los datos se cargan automáticamente desde el bucket',
    S3_SYNC_INFO: 'Los cambios en las etiquetas se guardan tanto localmente como en la nube para mayor seguridad'
  },
  
  // Colores de la aplicación
  COLORS: {
    PRIMARY: '#1976d2',
    SECONDARY: '#dc004e',
    SUCCESS: '#2e7d32',
    WARNING: '#ed6c02',
    ERROR: '#d32f2f',
    INFO: '#0288d1'
  }
};

export default config;
