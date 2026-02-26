import React, { useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import axios from 'axios';

/**
 * Página de callback tras login OAuth.
 * Recibe ?token=... desde el backend y guarda el token; luego redirige a la app.
 */
const AuthCallback = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');
  const error = searchParams.get('error');

  useEffect(() => {
    if (error) {
      navigate(`/login?error=${encodeURIComponent(error)}`, { replace: true });
      return;
    }
    if (token) {
      localStorage.setItem('token', token);
      axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
      navigate('/', { replace: true });
      window.location.reload();
    } else {
      navigate('/login', { replace: true });
    }
  }, [token, error, navigate]);

  return (
    <div style={{ padding: 24, textAlign: 'center' }}>
      Completando inicio de sesión...
    </div>
  );
};

export default AuthCallback;
