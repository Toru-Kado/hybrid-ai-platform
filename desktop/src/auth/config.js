export const AUTH_ENABLED = import.meta.env.VITE_AUTH_MODE === "cognito";

export const COGNITO_CONFIG = AUTH_ENABLED
  ? {
      userPoolId: import.meta.env.VITE_COGNITO_USER_POOL_ID,
      clientId: import.meta.env.VITE_COGNITO_CLIENT_ID,
    }
  : null;
