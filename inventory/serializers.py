from rest_framework import serializers
from .models import Item, Cart, CartItem, PurchaseLog


class ItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = Item
        fields = ["id", "name", "price", "quantity"]


class CartItemSerializer(serializers.ModelSerializer):
    item = ItemSerializer()

    class Meta:
        model = CartItem
        fields = ["id", "item", "quantity"]


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True, source="items.all")

    class Meta:
        model = Cart
        fields = ["id", "user_id", "is_active", "items"]


class PurchaseLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = PurchaseLog
        fields = ["id", "user_id", "item", "quantity", "purchase_price", "purchased_at"]
