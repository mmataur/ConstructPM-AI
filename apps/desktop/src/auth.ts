import { InMemoryWebStorage, UserManager, WebStorageStateStore } from 'oidc-client-ts';
import { invoke, isTauri } from '@tauri-apps/api/core';

const issuer = import.meta.env.VITE_OIDC_ISSUER || '';
const clientId = import.meta.env.VITE_OIDC_CLIENT_ID || '';
function browserManager() {
  return new UserManager({authority:issuer, client_id:clientId, redirect_uri:`${location.origin}/`, response_type:'code', scope:'openid profile email',
    userStore:new WebStorageStateStore({store:new InMemoryWebStorage()}), stateStore:new WebStorageStateStore({store:sessionStorage}), automaticSilentRenew:false});
}
export async function oidcSignIn() {
  if (!issuer || !clientId) throw new Error('Your administrator must configure the identity provider and native/public client ID.');
  if (isTauri()) return await invoke<string>('oidc_sign_in', {issuer, clientId});
  await browserManager().signinRedirect();
  return '';
}
export async function completeRedirect() {
  if (!location.search.includes('code=') && !location.search.includes('error=')) return '';
  const user = await browserManager().signinRedirectCallback();
  history.replaceState({}, '', '/');
  return user.access_token;
}
