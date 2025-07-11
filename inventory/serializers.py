from rest_framework import serializers
from inventory.models import Item, Cart, CartItem, PurchaseLog
from django.core.validators import MinValueValidator


class ItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = Item
        fields = ["id", "name", "price", "quantity"]
        extra_kwargs = {"price": {"min_value": 0.01}, "quantity": {"min_value": 0}}


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
    item = ItemSerializer()
    is_out_of_stock = serializers.SerializerMethodField()
    current_price_diff = serializers.SerializerMethodField()
    price_changed = serializers.SerializerMethodField()
    stock_changed = serializers.SerializerMethodField()
    available_quantity = serializers.SerializerMethodField()
    current_item_total = serializers.SerializerMethodField()

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
            "available_quantity",
            "current_item_total",
        ]

    def get_available_quantity(self, obj):
        return obj.item.quantity

    def get_current_item_total(self, obj):
        return (
            float(obj.item.price) * min(obj.quantity, obj.item.quantity)
            if obj.item.quantity > 0
            else 0
        )

    def get_total_price(self, obj):
        return sum(item.item.price * item.quantity for item in obj.items.all())

    def get_has_changes(self, obj):
        return any(
            item.item.price != item.price_at_addition
            or item.item.quantity < item.quantity
            for item in obj.items.all()
        )


class PurchaseLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = PurchaseLog
        fields = ["id", "user_id", "item", "quantity", "purchase_price", "purchased_at"]
        extra_kwargs = {
            "quantity": {"min_value": 1},
            "purchase_price": {"min_value": 0.01},
        }
