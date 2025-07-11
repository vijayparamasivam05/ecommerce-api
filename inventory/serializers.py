from rest_framework import serializers
from .models import Item, Cart, CartItem, PurchaseLog


class ItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = Item
        fields = ["id", "name", "price", "quantity"]


class CartItemDetailSerializer(serializers.ModelSerializer):
    item = ItemSerializer()
    is_out_of_stock = serializers.SerializerMethodField()
    current_price_diff = serializers.SerializerMethodField()
    price_changed = serializers.SerializerMethodField()
    stock_changed = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = [
            "id",
            "item",
            "quantity",
            "is_out_of_stock",
            "price_at_addition",
            "current_price_diff",
            "price_changed",
            "stock_changed",
        ]

    def get_is_out_of_stock(self, obj):
        return obj.item.quantity < obj.quantity

    def get_current_price_diff(self, obj):
        return float(obj.item.price - obj.price_at_addition)

    def get_price_changed(self, obj):
        return obj.item.price != obj.price_at_addition

    def get_stock_changed(self, obj):
        return obj.item.quantity < obj.quantity


class CartDetailSerializer(serializers.ModelSerializer):
    items = CartItemDetailSerializer(many=True, source="items.all")
    total_price = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = ["id", "user_id", "is_active", "items", "total_price"]

    def get_total_price(self, obj):
        return sum(item.item.price * item.quantity for item in obj.items.all())


class PurchaseLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = PurchaseLog
        fields = ["id", "user_id", "item", "quantity", "purchase_price", "purchased_at"]
