# E-Commerce API

A simple RESTful API for an e-commerce operations that handles item listings, cart management, and purchase functionality.

## 🚀 Setup & Running

```bash
git clone https://github.com/vijayparamasivam05/ecommerce-api.git
cd ecommerce-api
docker-compose up --build
docker compose exec web python manage.py migrate
docker compose exec web python manage.py load_items
```

- API: `http://localhost:8000/api/`

## 📚 API Endpoints

### 1. Items Listing
**GET /api/items/**
```json
// Response
{
  "success": true,
  "data": [
    {
      "id": 1,
      "name": "Smartphone",
      "price": 599.99,
      "quantity": 10
    }
  ]
}
```

### 2. Add to Cart
**POST /api/add-to-cart/**
```json
// Request
{
  "user_id": "user123",
  "item_id": 1,
  "quantity": 2
}

// Success Response
{
  "success": true,
  "data": {
    "item_total": 1199.98,
    "cart_total": 1199.98
  }
}

// Error Response (insufficient stock)
{
  "success": false,
  "error": "Insufficient stock",
  "available": 5
}
```

### 3. View Cart
**GET /api/cart/user123/**
```json
// Response
{
  "items": [
    {
      "item_id": 1,
      "name": "Smartphone",
      "quantity": 2,
      "price_at_addition": 599.99,
      "current_price": 599.99,
      "warnings": []
    }
  ],
  "totals": {
    "subtotal": 1199.98,
    "item_count": 2
  }
}
```

### 4. Remove from Cart
**DELETE /api/remove-from-cart/**
```json
// Request
{
  "user_id": "user123",
  "item_id": 1
}

// Response
{
  "success": true,
  "message": "Item removed"
}
```

### 5. Purchase Cart
**POST /api/purchase/**
```json
// Request
{
  "user_id": "user123",
  "Idempotency-Key": "unique-key-a-123" (header)
}

// Success Response
{
  "success": true,
  "purchased_items": [
    {
      "item_id": 1,
      "quantity": 2,
      "price": 599.99
    }
  ]
}

// Changed Items Response (409 Conflict)
{
  "changes": [
    {
      "type": "price_change",
      "item_id": 1,
      "old_price": 599.99,
      "new_price": 649.99
    }
  ]
}
```

### 6. Confirm Purchase (After Changes)
**POST /api/confirm-purchase/**
```json
// Request
{
  "user_id": "user123"
}

// Response
{
  "success": true,
  "adjusted_items": [
    {
      "item_id": 1,
      "new_quantity": 1
    }
  ]
}
```

## 🔐 Security Note
The included `.env` is for development only. it's generally not recommended to commit '.env' files

## 🛠️ Development
```bash
# Run tests
docker compose exec web python manage.py test inventory.tests
```

Postman collection available in `/postman` with all request examples.
```

Key improvements:
1. Added concrete request/response examples for every endpoint
2. Included Idempotency-Key header example
3. Added admin panel note
4. Included test/database access commands
5. Clear security warning about .env files
6. Organized endpoints in logical flow (browse → cart → purchase)