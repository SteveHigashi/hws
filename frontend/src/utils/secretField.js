// Attributes for a field that holds a secret which is NOT this site's login password:
// an AI provider API key, a Higashi Live key, an SSH password for someone else's server.
//
// Why this exists: on 2026-09-23 Chrome autofilled the saved dashboard login password
// into the Live key field and into "Ask your data", because both were type="password"
// with nothing telling the browser otherwise. The fields then showed ~14 dots — which
// reads as "already configured" — and the Live one showed "That is not a Live key" in
// red on an install whose key was perfectly fine. A red mark over a working thing.
//
// autoComplete="off" is not enough; Chrome has ignored it on password inputs for years.
// "new-password" is the one it honours, and the data-* attributes are what the common
// password managers look for. None of this is a security control — it is the browser
// being told what kind of field this is so it stops guessing wrong.

export const SECRET_FIELD_PROPS = {
  autoComplete: "new-password",
  autoCorrect: "off",
  autoCapitalize: "off",
  spellCheck: false,
  "data-1p-ignore": "",        // 1Password
  "data-lpignore": "true",     // LastPass
  "data-bwignore": "true",     // Bitwarden
  "data-form-type": "other",   // Dashlane
};

/** The same, with a field name that does not look like a credential form. */
export function secretFieldProps(name) {
  return { ...SECRET_FIELD_PROPS, name };
}

export default SECRET_FIELD_PROPS;
