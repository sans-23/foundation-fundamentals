import Keycloak from 'keycloak-js';

/**
 * Keycloak JS Adapter Configuration
 * 
 * This initializes the Keycloak client-side adapter. In a real production setup,
 * you would point this to your Keycloak server's realm and the "public" client
 * you created in the Keycloak Admin Console.
 * 
 * Key Concepts:
 * - `url`: The base URL of your Keycloak server
 * - `realm`: The Keycloak realm that manages users for this app
 * - `clientId`: The Client ID registered in Keycloak (must be a "public" client)
 * 
 * The adapter handles the entire OAuth2 Authorization Code + PKCE flow:
 * 1. Redirects user to Keycloak login page
 * 2. Receives the authorization code after successful login
 * 3. Exchanges the code for Access Token + ID Token + Refresh Token
 * 4. Stores tokens in memory (NOT localStorage for security)
 * 5. Automatically refreshes tokens before they expire
 */
const keycloak = new Keycloak({
  url: import.meta.env.VITE_KEYCLOAK_URL || 'http://localhost:8080',
  realm: import.meta.env.VITE_KEYCLOAK_REALM || 'secureorder',
  clientId: import.meta.env.VITE_KEYCLOAK_CLIENT_ID || 'frontend-app',
});

export default keycloak;
