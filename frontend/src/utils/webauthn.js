// Browser side of passkey sign-in. The server speaks base64url (the WebAuthn JSON
// dialect); the browser API speaks ArrayBuffer, so everything crossing that line is
// converted here and nowhere else.
import api from "./api";

export const passkeysSupported = () =>
  typeof window !== "undefined" && !!window.PublicKeyCredential && !!navigator.credentials;

const toBuffer = (value) => {
  const padded = value.replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(padded + "=".repeat((4 - (padded.length % 4)) % 4));
  return Uint8Array.from(raw, (c) => c.charCodeAt(0)).buffer;
};

const toBase64url = (buffer) =>
  btoa(String.fromCharCode(...new Uint8Array(buffer)))
    .replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");

const decodeOptions = (options) => ({
  ...options,
  challenge: toBuffer(options.challenge),
  ...(options.user ? { user: { ...options.user, id: toBuffer(options.user.id) } } : {}),
  ...(options.excludeCredentials
    ? { excludeCredentials: options.excludeCredentials.map((c) => ({ ...c, id: toBuffer(c.id) })) }
    : {}),
  ...(options.allowCredentials
    ? { allowCredentials: options.allowCredentials.map((c) => ({ ...c, id: toBuffer(c.id) })) }
    : {}),
});

const encodeCredential = (credential) => {
  const response = credential.response;
  const body = {
    id: credential.id,
    rawId: toBase64url(credential.rawId),
    type: credential.type,
    response: { clientDataJSON: toBase64url(response.clientDataJSON) },
  };
  if (response.attestationObject) {
    body.response.attestationObject = toBase64url(response.attestationObject);
    if (response.getTransports) body.response.transports = response.getTransports();
  } else {
    body.response.authenticatorData = toBase64url(response.authenticatorData);
    body.response.signature = toBase64url(response.signature);
    if (response.userHandle) body.response.userHandle = toBase64url(response.userHandle);
  }
  return body;
};

// Signed in already: add a passkey to this account.
export async function registerPasskey(name) {
  const { data } = await api.post("/auth/passkeys/register/options", {});
  const credential = await navigator.credentials.create({ publicKey: decodeOptions(data.options) });
  if (!credential) throw new Error("No passkey was created");
  await api.post("/auth/passkeys/register/verify", {
    state: data.state,
    credential: encodeCredential(credential),
    name: name || "Passkey",
  });
}

// Not signed in: prove a passkey and get a token back.
export async function signInWithPasskey(email) {
  const { data } = await api.post("/auth/passkeys/login/options", { email: email || null });
  const credential = await navigator.credentials.get({ publicKey: decodeOptions(data.options) });
  if (!credential) throw new Error("No passkey was used");
  const { data: token } = await api.post("/auth/passkeys/login/verify", {
    state: data.state,
    credential: encodeCredential(credential),
  });
  return token;
}
