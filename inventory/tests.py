from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from inventory.models import Item, Cart, CartItem, PurchaseLog
from decimal import Decimal, ROUND_HALF_UP


class CartSystemTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.item1 = Item.objects.create(
            name="Test Item 1",
            price=Decimal("10.99").quantize(Decimal("0.01")),
            quantity=5,
        )
        self.item2 = Item.objects.create(
            name="Test Item 2",
            price=Decimal("5.50").quantize(Decimal("0.01")),
            quantity=3,
        )

        self.user_id = "test_user_123"

        self.add_to_cart_url = reverse("add-to-cart")
        self.view_cart_url = lambda user_id: reverse("view-cart", args=[user_id])
        self.purchase_url = reverse("purchase-cart")
        self.confirm_purchase_url = reverse("confirm-purchase")

    def assertDecimalEqual(self, first, second, msg=None):
        """Custom assertion for Decimal comparison with 2 decimal places"""
        if isinstance(first, (float, str)):
            first = Decimal(str(first)).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        if isinstance(second, (float, str)):
            second = Decimal(str(second)).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        self.assertEqual(first, second, msg)

    def test_add_item_to_cart(self):
        """Test adding an item to cart successfully"""
        data = {"user_id": self.user_id, "item_id": self.item1.id, "quantity": 2}

        response = self.client.post(self.add_to_cart_url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["data"]["quantity"], 2)
        self.assertDecimalEqual(response.data["data"]["item_total"], Decimal("21.98"))

        cart = Cart.objects.get(user_id=self.user_id)
        self.assertTrue(cart.is_active)

        cart_item = CartItem.objects.get(cart=cart, item=self.item1)
        self.assertEqual(cart_item.quantity, 2)
        self.assertEqual(cart_item.price_at_addition, Decimal("10.99"))

    def test_add_item_insufficient_stock(self):
        """Test adding more items than available stock"""
        data = {
            "user_id": self.user_id,
            "item_id": self.item1.id,
            "quantity": 10,
        }

        response = self.client.post(self.add_to_cart_url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data["success"])
        self.assertEqual(response.data["error"], "Insufficient stock")
        self.assertEqual(response.data["available"], 5)

    def test_view_cart(self):
        """Test viewing cart contents"""

        self.client.post(
            self.add_to_cart_url,
            {"user_id": self.user_id, "item_id": self.item1.id, "quantity": 2},
            format="json",
        )

        response = self.client.get(self.view_cart_url(self.user_id))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertEqual(len(response.data["data"]["items"]), 1)
        self.assertDecimalEqual(
            response.data["data"]["totals"]["subtotal"], Decimal("21.98")
        )

    def test_purchase_cart_success(self):
        """Test successful cart purchase"""

        self.client.post(
            self.add_to_cart_url,
            {"user_id": self.user_id, "item_id": self.item1.id, "quantity": 2},
            format="json",
        )
        self.client.post(
            self.add_to_cart_url,
            {"user_id": self.user_id, "item_id": self.item2.id, "quantity": 1},
            format="json",
        )

        response = self.client.post(
            self.purchase_url, {"user_id": self.user_id}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertEqual(len(response.data["purchased_items"]), 2)
        self.assertDecimalEqual(response.data["purchase_total"], Decimal("27.48"))

        cart = Cart.objects.get(user_id=self.user_id)
        self.assertFalse(cart.is_active)

        item1 = Item.objects.get(id=self.item1.id)
        self.assertEqual(item1.quantity, 3)

        self.assertEqual(PurchaseLog.objects.count(), 2)
        self.assertEqual(PurchaseLog.objects.first().purchase_price, Decimal("10.99"))

    def test_purchase_with_changes(self):
        """Test purchase when items have changed (price or stock)"""

        self.client.post(
            self.add_to_cart_url,
            {"user_id": self.user_id, "item_id": self.item1.id, "quantity": 2},
            format="json",
        )

        self.item1.price = Decimal("12.99").quantize(Decimal("0.01"))
        self.item1.quantity = 1
        self.item1.save()

        response = self.client.post(
            self.purchase_url, {"user_id": self.user_id}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertFalse(response.data["success"])
        self.assertTrue(response.data["requires_confirmation"])
        self.assertEqual(len(response.data["changes"]), 2)

        price_change = next(
            c for c in response.data["changes"] if c["type"] == "price_change"
        )
        self.assertDecimalEqual(price_change["old_price"], Decimal("10.99"))
        self.assertDecimalEqual(price_change["new_price"], Decimal("12.99"))

        cart = Cart.objects.get(user_id=self.user_id)
        self.assertTrue(cart.is_active)

    def test_confirm_purchase_with_changes(self):
        """Test confirming purchase after changes"""

        self.client.post(
            self.add_to_cart_url,
            {"user_id": self.user_id, "item_id": self.item1.id, "quantity": 3},
            format="json",
        )

        self.item1.quantity = 2
        self.item1.save()

        response = self.client.post(
            self.confirm_purchase_url, {"user_id": self.user_id}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertEqual(len(response.data["warnings"]), 1)

        warning = response.data["warnings"][0]
        self.assertEqual(warning["type"], "quantity_adjusted")
        self.assertEqual(warning["requested"], 3)
        self.assertEqual(warning["adjusted_to"], 2)

        purchase_log = PurchaseLog.objects.first()
        self.assertEqual(purchase_log.quantity, 2)
        self.assertEqual(purchase_log.purchase_price, Decimal("10.99"))

        item1 = Item.objects.get(id=self.item1.id)
        self.assertEqual(item1.quantity, 0)

    def test_remove_from_cart(self):
        """Test removing an item from cart"""

        self.client.post(
            self.add_to_cart_url,
            {"user_id": self.user_id, "item_id": self.item1.id, "quantity": 2},
            format="json",
        )
        self.client.post(
            self.add_to_cart_url,
            {"user_id": self.user_id, "item_id": self.item2.id, "quantity": 1},
            format="json",
        )

        response = self.client.delete(
            reverse("remove-from-cart"),
            {"user_id": self.user_id, "item_id": self.item1.id},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])

        cart = Cart.objects.get(user_id=self.user_id)
        self.assertEqual(cart.items.count(), 1)
        self.assertEqual(cart.items.first().item.id, self.item2.id)
