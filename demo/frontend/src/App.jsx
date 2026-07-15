import { useState, useEffect } from 'react';
import keycloak from './keycloak';
import OrderForm from './components/OrderForm';
import InventoryView from './components/InventoryView';

/**
 * Main Application Component
 * 
 * This is where the Keycloak login flow is orchestrated.
 * 
 * On mount, we call `keycloak.init()` with:
 * - `onLoad: 'login-required'` — forces a redirect to the Keycloak login page
 *   if the user doesn't have a valid session. There's no "unauthenticated" state.
 * - `pkceMethod: 'S256'` — uses the PKCE extension (Proof Key for Code Exchange)
 *   which is mandatory for public clients (SPAs) to prevent authorization code
 *   interception attacks.
 * - `checkLoginIframe: false` — disables the hidden iframe that Keycloak uses to
 *   detect SSO session changes. Disabled here for simplicity in dev mode.
 * 
 * Once authenticated:
 * - `keycloak.token` contains the JWT Access Token
 * - `keycloak.tokenParsed` contains the decoded JWT payload (claims)
 * - `keycloak.idTokenParsed` contains user profile info from the ID Token
 */
function App() {
  const [authenticated, setAuthenticated] = useState(false);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('orders');

  useEffect(() => {
    keycloak
      .init({
        onLoad: 'login-required',
        pkceMethod: 'S256',
        checkLoginIframe: false,
      })
      .then((auth) => {
        setAuthenticated(auth);
        setLoading(false);

        if (auth) {
          console.log('✅ Authenticated!');
          console.log('Access Token (first 50 chars):', keycloak.token?.substring(0, 50) + '...');
          console.log('Token Parsed (Claims):', keycloak.tokenParsed);
        }
      })
      .catch((err) => {
        console.error('Keycloak init failed:', err);
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <div className="loading-screen">
        <div className="spinner"></div>
        <p>Connecting to Identity Provider...</p>
      </div>
    );
  }

  if (!authenticated) {
    return (
      <div className="loading-screen">
        <p>Authentication failed. Please try again.</p>
        <button onClick={() => keycloak.login()}>Login</button>
      </div>
    );
  }

  const userInfo = keycloak.tokenParsed;

  return (
    <div className="app">
      {/* Header with user info and logout */}
      <header className="app-header">
        <div className="header-left">
          <h1>🔐 SecureOrder Dashboard</h1>
        </div>
        <div className="header-right">
          <div className="user-info">
            <span className="user-name">
              {userInfo?.preferred_username || userInfo?.name || 'User'}
            </span>
            <span className="user-email">{userInfo?.email || ''}</span>
          </div>
          <button className="logout-btn" onClick={() => keycloak.logout()}>
            Logout
          </button>
        </div>
      </header>

      {/* Token Inspector */}
      <section className="token-inspector card">
        <h2>🔑 JWT Access Token (Decoded Claims)</h2>
        <p className="hint">
          This is the decoded payload of your Access Token. The backend validates the
          cryptographic signature using Keycloak's public keys, then reads these claims.
        </p>
        <pre>{JSON.stringify(userInfo, null, 2)}</pre>
      </section>

      {/* Tab Navigation */}
      <nav className="tab-nav">
        <button
          className={activeTab === 'orders' ? 'active' : ''}
          onClick={() => setActiveTab('orders')}
        >
          📦 Orders
        </button>
        <button
          className={activeTab === 'inventory' ? 'active' : ''}
          onClick={() => setActiveTab('inventory')}
        >
          🏭 Inventory
        </button>
      </nav>

      {/* Tab Content */}
      <main className="content">
        {activeTab === 'orders' && <OrderForm />}
        {activeTab === 'inventory' && <InventoryView />}
      </main>
    </div>
  );
}

export default App;
