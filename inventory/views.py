from django.db import transaction
from django.core.cache import cache

from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.decorators import api_view

from .models import Item, Cart, CartItem, PurchaseLog
from .serializers import (
    ItemSerializer,
    CartDetailSerializer,
)


@api_view(["GET"])
def item_list(request):
    items = Item.objects.filter(quantity__gt=0).order_by("id")
    serializer = ItemSerializer(items, many=True)
    return Response(serializer.data)


@api_view(["POST"])
@transaction.atomic
def add_to_cart(request):
    user_id = request.data.get("user_id")
    item_id = request.data.get("item_id")
    quantity = int(request.data.get("quantity", 1))

    try:
        item = Item.objects.select_for_update().get(id=item_id)

        if item.quantity < quantity:
            return Response(
                {"error": f"Not enough stock. Only {item.quantity} available"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cart, _ = Cart.objects.get_or_create(
            user_id=user_id, is_active=True, defaults={"user_id": user_id}
        )

        cart_item, created = CartItem.objects.get_or_create(
            cart=cart,
            item=item,
            defaults={
                "quantity": quantity,
                "price_at_addition": item.price,
            },
        )

        if not created:
            if (cart_item.quantity + quantity) > item.quantity:
                return Response(
                    {
                        "error": f"Cannot add {quantity} more. Would exceed available stock"
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            cart_item.quantity += quantity
            cart_item.price_at_addition = item.price
            cart_item.save()

        return Response(
            {
                "success": "Item added to cart",
                "remaining_stock": item.quantity,
                "cart_quantity": cart_item.quantity,
                "price_at_addition": float(cart_item.price_at_addition),
            },
            status=status.HTTP_200_OK,
        )

    except Item.DoesNotExist:
        return Response({"error": "Item not found"}, status=status.HTTP_404_NOT_FOUND)


@api_view(["GET"])
def view_cart(request, user_id):
    try:
        cart = Cart.objects.get(user_id=user_id, is_active=True)
        serializer = CartDetailSerializer(cart)
        return Response(serializer.data)
    except Cart.DoesNotExist:
        return Response(
            {"error": "No active cart found"}, status=status.HTTP_404_NOT_FOUND
        )


@api_view(["POST"])
@transaction.atomic
def purchase_cart(request):
    user_id = request.data.get("user_id")
    idempotency_key = request.headers.get("Idempotency-Key")

    if idempotency_key:
        cache_key = f"purchase_{idempotency_key}"
        if cache.get(cache_key):
            return Response(
                {"status": "already_processed"}, status=status.HTTP_208_ALREADY_REPORTED
            )
        cache.set(cache_key, True, timeout=86400)

    try:
        cart = Cart.objects.get(user_id=user_id, is_active=True)
    except Cart.DoesNotExist:
        return Response(
            {"error": "No active cart found"}, status=status.HTTP_404_NOT_FOUND
        )

    changes = []
    for cart_item in cart.items.all():
        item = cart_item.item
        if item.price != cart_item.price_at_addition:
            changes.append(
                {
                    "item_id": item.id,
                    "item_name": item.name,
                    "old_price": float(cart_item.price_at_addition),
                    "new_price": float(item.price),
                    "type": "price_change",
                }
            )
        if item.quantity < cart_item.quantity:
            changes.append(
                {
                    "item_id": item.id,
                    "item_name": item.name,
                    "requested_quantity": cart_item.quantity,
                    "available_quantity": item.quantity,
                    "type": "stock_change",
                }
            )

    if changes:
        return Response(
            {
                "error": "Cart items have changed",
                "changes": changes,
                "requires_confirmation": True,
            },
            status=status.HTTP_409_CONFLICT,
        )

    for cart_item in cart.items.all():
        item = cart_item.item
        item.quantity -= cart_item.quantity
        item.save()

        PurchaseLog.objects.create(
            user_id=user_id,
            item=item,
            quantity=cart_item.quantity,
            purchase_price=cart_item.price_at_addition,
        )

    cart.is_active = False
    cart.save()

    return Response({"success": "Purchase completed"}, status=status.HTTP_200_OK)


@api_view(["POST"])
@transaction.atomic
def confirm_purchase_with_changes(request):
    user_id = request.data.get("user_id")

    try:
        cart = Cart.objects.get(user_id=user_id, is_active=True)
    except Cart.DoesNotExist:
        return Response(
            {"error": "No active cart found"}, status=status.HTTP_404_NOT_FOUND
        )

    for cart_item in cart.items.all():
        item = cart_item.item
        if item.quantity < cart_item.quantity:
            if item.quantity > 0:
                cart_item.quantity = item.quantity
                cart_item.save()
            else:
                cart_item.delete()

    for cart_item in cart.items.all():
        item = cart_item.item
        item.quantity -= cart_item.quantity
        item.save()

        PurchaseLog.objects.create(
            user_id=user_id,
            item=item,
            quantity=cart_item.quantity,
            purchase_price=item.price,
        )

    cart.is_active = False
    cart.save()

    return Response(
        {
            "success": "Purchase completed with updated items",
            "message": "Some items were updated based on current availability",
        },
        status=status.HTTP_200_OK,
    )


@api_view(["DELETE"])
@transaction.atomic
def remove_from_cart(request):
    user_id = request.data.get("user_id")
    item_id = request.data.get("item_id")

    try:
        cart = Cart.objects.get(user_id=user_id, is_active=True)
        cart_item = CartItem.objects.get(cart=cart, item_id=item_id)
        cart_item.delete()

        return Response(
            {"success": "Item removed from cart"}, status=status.HTTP_200_OK
        )

    except Cart.DoesNotExist:
        return Response(
            {"error": "No active cart found"}, status=status.HTTP_404_NOT_FOUND
        )
    except CartItem.DoesNotExist:
        return Response({"error": "Item not in cart"}, status=status.HTTP_404_NOT_FOUND)
