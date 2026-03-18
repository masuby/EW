export const API_BASE_URL = 'http://localhost:8083';

export const API_URLS = {
  health: `${API_BASE_URL}/api/health`,
  login: `${API_BASE_URL}/api/auth/login`,
  me: `${API_BASE_URL}/api/auth/me`,
  tma722e4Generate: `${API_BASE_URL}/api/bulletins/tma/722e4/generate`,
  dmdMultiriskGenerate: `${API_BASE_URL}/api/bulletins/dmd/multirisk/generate`,
  spatialIntersections: `${API_BASE_URL}/api/maps/intersections`,
  historyTma722e4: `${API_BASE_URL}/api/history/tma_722e4`,
  historyDmdMultirisk: `${API_BASE_URL}/api/history/dmd_multirisk`,
} as const;

