import { useState } from 'react';
import { api } from '../api';

/**
 * InventoryView Component
 * 
 * Demonstrates:
 * - Sending authenticated GET requests to the Inventory Service
 * - The Inventory Service first checks Redis cache, then falls back to PostgreSQL
 * - Observing Cache Hit vs Cache Miss in the Inventory Service terminal logs
 */
export default function InventoryView() {
  const [productId, setProductId] = useState('');
  const [inventory, setInventory] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleCheck = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setInventory(null);

    try {
      const data = await api.get(`/api/inventory/${productId}`);
      setInventory(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="card">
      <h2>🏭 Check Inventory</h2>
      <form onSubmit={handleCheck}>
        <div className="form-group">
          <label htmlFor="checkProductId">Product ID</label>
          <input
            id="checkProductId"
            type="text"
            value={productId}
            onChange={(e) => setProductId(e.target.value)}
            placeholder="e.g., PROD-001"
            required
          />
        </div>
        <button type="submit" disabled={loading}>
          {loading ? 'Checking...' : 'Check Stock'}
        </button>
      </form>

      {inventory && (
        <div className="result success">
          <h3>📊 Stock Level</h3>
          <p><strong>Product:</strong> {inventory.product_id}</p>
          <p><strong>Available Stock:</strong> {inventory.stock}</p>
        </div>
      )}
      {error && (
        <div className="result error">
          <h3>❌ Error</h3>
          <p>{error}</p>
        </div>
      )}
    </div>
  );
}
