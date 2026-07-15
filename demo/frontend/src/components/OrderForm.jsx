import { useState } from 'react';
import { api } from '../api';

/**
 * OrderForm Component
 * 
 * Demonstrates:
 * - Sending authenticated POST requests to the Order Service
 * - The JWT token is automatically attached by our api.js wrapper
 * - The backend extracts the user_id from the 'sub' claim in the JWT
 */
export default function OrderForm() {
  const [productId, setProductId] = useState('');
  const [quantity, setQuantity] = useState(1);
  const [totalPrice, setTotalPrice] = useState(0);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const data = await api.post('/api/orders', {
        product_id: productId,
        quantity: parseInt(quantity),
        total_price: parseFloat(totalPrice),
      });
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="card">
      <h2>📦 Place Order</h2>
      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label htmlFor="productId">Product ID</label>
          <input
            id="productId"
            type="text"
            value={productId}
            onChange={(e) => setProductId(e.target.value)}
            placeholder="e.g., PROD-001"
            required
          />
        </div>
        <div className="form-group">
          <label htmlFor="quantity">Quantity</label>
          <input
            id="quantity"
            type="number"
            value={quantity}
            onChange={(e) => setQuantity(e.target.value)}
            min="1"
            required
          />
        </div>
        <div className="form-group">
          <label htmlFor="totalPrice">Total Price ($)</label>
          <input
            id="totalPrice"
            type="number"
            step="0.01"
            value={totalPrice}
            onChange={(e) => setTotalPrice(e.target.value)}
            min="0"
            required
          />
        </div>
        <button type="submit" disabled={loading}>
          {loading ? 'Placing Order...' : 'Place Order'}
        </button>
      </form>

      {result && (
        <div className="result success">
          <h3>✅ Order Created!</h3>
          <pre>{JSON.stringify(result, null, 2)}</pre>
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
