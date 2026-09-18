/**
 * Smoke test ligero: evita cargar axios ESM vía Dashboard/api.
 */
test('AuthContext exporta useAuth', () => {
  jest.isolateModules(() => {
    jest.doMock('./utils/axios', () => ({
      __esModule: true,
      default: {
        get: jest.fn(() => Promise.reject(new Error('no session'))),
        post: jest.fn(),
        defaults: { headers: { common: {} } },
        interceptors: {
          request: { use: jest.fn() },
          response: { use: jest.fn() },
        },
      },
    }));
    // eslint-disable-next-line global-require
    const { useAuth, AuthProvider } = require('./auth/AuthContext');
    expect(typeof useAuth).toBe('function');
    expect(typeof AuthProvider).toBe('function');
  });
});
