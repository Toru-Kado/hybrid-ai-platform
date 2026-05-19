import {
  CognitoUserPool,
  CognitoUser,
  AuthenticationDetails,
  CognitoUserAttribute,
} from "amazon-cognito-identity-js";
import { AUTH_ENABLED, COGNITO_CONFIG } from "./config";

let userPool = null;

function getUserPool() {
  if (!userPool && AUTH_ENABLED) {
    userPool = new CognitoUserPool({
      UserPoolId: COGNITO_CONFIG.userPoolId,
      ClientId: COGNITO_CONFIG.clientId,
    });
  }
  return userPool;
}

export function signIn(email, password) {
  return new Promise((resolve, reject) => {
    const pool = getUserPool();
    if (!pool) return reject(new Error("Auth not configured"));

    const user = new CognitoUser({ Username: email, Pool: pool });
    const authDetails = new AuthenticationDetails({
      Username: email,
      Password: password,
    });

    user.authenticateUser(authDetails, {
      onSuccess: (session) => resolve(session),
      onFailure: (err) => reject(err),
      newPasswordRequired: () => {
        reject(new Error("Password change required. Please contact support."));
      },
    });
  });
}

export function signUp(email, password) {
  return new Promise((resolve, reject) => {
    const pool = getUserPool();
    if (!pool) return reject(new Error("Auth not configured"));

    const attributes = [
      new CognitoUserAttribute({ Name: "email", Value: email }),
    ];

    pool.signUp(email, password, attributes, null, (err, result) => {
      if (err) return reject(err);
      resolve(result);
    });
  });
}

export function confirmSignUp(email, code) {
  return new Promise((resolve, reject) => {
    const pool = getUserPool();
    if (!pool) return reject(new Error("Auth not configured"));

    const user = new CognitoUser({ Username: email, Pool: pool });
    user.confirmRegistration(code, true, (err, result) => {
      if (err) return reject(err);
      resolve(result);
    });
  });
}

export function signOut() {
  const pool = getUserPool();
  if (!pool) return;
  const user = pool.getCurrentUser();
  if (user) user.signOut();
}

export function getCurrentSession() {
  return new Promise((resolve) => {
    const pool = getUserPool();
    if (!pool) return resolve(null);

    const user = pool.getCurrentUser();
    if (!user) return resolve(null);

    user.getSession((err, session) => {
      if (err || !session?.isValid()) return resolve(null);
      resolve(session);
    });
  });
}

export async function getAccessToken() {
  const session = await getCurrentSession();
  if (!session) return null;

  const accessToken = session.getAccessToken();
  const exp = accessToken.getExpiration();
  const now = Math.floor(Date.now() / 1000);

  // If token expires within 60 seconds, refresh it
  if (exp - now < 60) {
    const refreshed = await refreshSession();
    if (refreshed) {
      return refreshed.getAccessToken().getJwtToken();
    }
    return null;
  }

  return accessToken.getJwtToken();
}

export function refreshSession() {
  return new Promise((resolve) => {
    const pool = getUserPool();
    if (!pool) return resolve(null);

    const user = pool.getCurrentUser();
    if (!user) return resolve(null);

    user.getSession((err, session) => {
      if (err || !session) return resolve(null);

      const refreshToken = session.getRefreshToken();
      user.refreshSession(refreshToken, (refreshErr, newSession) => {
        if (refreshErr) return resolve(null);
        resolve(newSession);
      });
    });
  });
}
