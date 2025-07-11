from django.db import transaction
from django.core.cache import cache
from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view
from inventory.models import Item, Cart, CartItem, PurchaseLog
from inventory.serializers import ItemSerializer, CartDetailSerializer


@api_view(["GET"])
def item_list(request):
    try:
        items = Item.objects.filter(quantity__gt=0).order_by("id")
        serializer = ItemSerializer(items, many=True)
        return Response(
            {"success": True, "data": serializer.data}, status=status.HTTP_200_OK
        )
    except Exception as e:
        return Response(
            {"success": False, "error": "Failed to retrieve items", "detail": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@transaction.atomic
def add_to_cart(request):
    required_fields = ["user_id", "item_id"]
    if not all(field in request.data for field in required_fields):
        return Response(
            {
                "success": False,
                "error": "Missing required fields",
                "required": required_fields,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        user_id = request.data["user_id"]
        item_id = request.data["item_id"]
        quantity = int(request.data.get("quantity", 1))

        if quantity <= 0:
            return Response(
                {"success": False, "error": "Quantity must be at least 1"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        item = Item.objects.select_for_update().get(id=item_id)

        if item.quantity < quantity:
            return Response(
                {
                    "success": False,
                    "error": "Insufficient stock",
                    "available": item.quantity,
                    "requested": quantity,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        cart, _ = Cart.objects.get_or_create(
            user_id=user_id, is_active=True, defaults={"user_id": user_id}
        )

        cart_item, created = CartItem.objects.get_or_create(
            cart=cart,
            item=item,
            defaults={"quantity": quantity, "price_at_addition": item.price},
        )

        if not created:
            new_quantity = cart_item.quantity + quantity
            if new_quantity > item.quantity:
                return Response(
                    {
                        "success": False,
                        "error": "Cannot add more items",
                        "available": item.quantity - cart_item.quantity,
                        "requested": quantity,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            cart_item.quantity = new_quantity
            cart_item.save()

        item_total = float(cart_item.price_at_addition) * cart_item.quantity
        cart_items = cart.items.all()
        cart_total = sum(
            float(item.price_at_addition) * item.quantity for item in cart_items
        )

        return Response(
            {
                "success": True,
                "message": "Item added to cart",
                "data": {
                    "cart_id": cart.id,
                    "item_id": item.id,
                    "quantity": cart_item.quantity,
                    "price_at_addition": float(cart_item.price_at_addition),
                    "item_total": round(item_total, 2),
                    "cart_total": round(cart_total, 2),
                    "cart_item_count": cart_items.count(),
                },
            },
            status=status.HTTP_200_OK,
        )

    except Item.DoesNotExist:
        return Response(
            {"success": False, "error": "Item not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"success": False, "error": "Failed to add item to cart", "detail": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
def view_cart(request, user_id):
    try:
        cart = Cart.objects.get(user_id=user_id, is_active=True)

        # Initialize response data
        response_data = {
            "success": True,
            "data": {
                "cart_id": cart.id,
                "user_id": cart.user_id,
                "items": [],
                "totals": {"subtotal": 0.0, "item_count": 0},
                "warnings": [],
            },
        }

        # Process each cart item
        for cart_item in cart.items.all():
            item = cart_item.item
            price_changed = item.price != cart_item.price_at_addition
            stock_changed = item.quantity < cart_item.quantity

            # Calculate item totals
            item_total = float(cart_item.price_at_addition) * cart_item.quantity
            current_item_total = (
                float(item.price) * min(cart_item.quantity, item.quantity)
                if item.quantity > 0
                else 0
            )

            # Build item data
            item_data = {
                "item_id": item.id,
                "name": item.name,
                "quantity": cart_item.quantity,
                "price_at_addition": float(cart_item.price_at_addition),
                "current_price": float(item.price),
                "item_total": round(item_total, 2),
                "current_item_total": round(current_item_total, 2),
                "available_quantity": item.quantity,
                "price_changed": price_changed,
                "stock_changed": stock_changed,
            }

            # Add warnings if changes detected
            if price_changed:
                response_data["data"]["warnings"].append(
                    {
                        "type": "price_change",
                        "item_id": item.id,
                        "name": item.name,
                        "old_price": float(cart_item.price_at_addition),
                        "new_price": float(item.price),
                        "difference": round(
                            float(item.price - cart_item.price_at_addition), 2
                        ),
                    }
                )

            if stock_changed:
                response_data["data"]["warnings"].append(
                    {
                        "type": "stock_change",
                        "item_id": item.id,
                        "name": item.name,
                        "requested_quantity": cart_item.quantity,
                        "available_quantity": item.quantity,
                        "difference": item.quantity - cart_item.quantity,
                    }
                )

            # Add to response items
            response_data["data"]["items"].append(item_data)

            # Update cart totals
            response_data["data"]["totals"]["subtotal"] += item_total
            response_data["data"]["totals"]["item_count"] += cart_item.quantity

        # Round totals
        response_data["data"]["totals"]["subtotal"] = round(
            response_data["data"]["totals"]["subtotal"], 2
        )

        # Add has_changes flag
        response_data["data"]["has_changes"] = (
            len(response_data["data"]["warnings"]) > 0
        )

        return Response(response_data, status=status.HTTP_200_OK)

    except Cart.DoesNotExist:
        return Response(
            {"success": False, "error": "No active cart found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"success": False, "error": "Failed to retrieve cart", "detail": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@transaction.atomic
def purchase_cart(request):
    if "user_id" not in request.data:
        return Response(
            {"success": False, "error": "user_id is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user_id = request.data["user_id"]
    idempotency_key = request.headers.get("Idempotency-Key")

    if idempotency_key:
        cache_key = f"purchase_{idempotency_key}"
        if cache.get(cache_key):
            return Response(
                {
                    "success": False,
                    "error": "Duplicate request detected",
                    "code": "duplicate_request",
                },
                status=status.HTTP_409_CONFLICT,
            )
        cache.set(cache_key, True, timeout=86400)

    try:
        cart = Cart.objects.get(user_id=user_id, is_active=True)
    except Cart.DoesNotExist:
        return Response(
            {"success": False, "error": "No active cart found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    changes = []
    for cart_item in cart.items.all():
        item = cart_item.item
        if item.price != cart_item.price_at_addition:
            changes.append(
                {
                    "item_id": item.id,
                    "name": item.name,
                    "type": "price_change",
                    "old_price": float(cart_item.price_at_addition),
                    "new_price": float(item.price),
                    "difference": float(item.price - cart_item.price_at_addition),
                }
            )
        if item.quantity < cart_item.quantity:
            changes.append(
                {
                    "item_id": item.id,
                    "name": item.name,
                    "type": "stock_change",
                    "requested": cart_item.quantity,
                    "available": item.quantity,
                    "difference": item.quantity - cart_item.quantity,
                }
            )

    if changes:
        # Calculate current cart total for the response
        cart_total = sum(
            float(item.price_at_addition) * item.quantity for item in cart.items.all()
        )
        return Response(
            {
                "success": False,
                "error": "Cart items have changed",
                "code": "cart_changes_detected",
                "changes": changes,
                "requires_confirmation": True,
                "cart_total": round(cart_total, 2),
            },
            status=status.HTTP_409_CONFLICT,
        )

    try:
        with transaction.atomic():
            purchased_items = []
            purchase_total = 0.0

            for cart_item in cart.items.all():
                item = cart_item.item
                item.quantity -= cart_item.quantity
                item.save()

                item_total = float(cart_item.price_at_addition) * cart_item.quantity
                purchase_total += item_total

                PurchaseLog.objects.create(
                    user_id=user_id,
                    item=item,
                    quantity=cart_item.quantity,
                    purchase_price=cart_item.price_at_addition,
                )
                purchased_items.append(
                    {
                        "item_id": item.id,
                        "name": item.name,
                        "quantity": cart_item.quantity,
                        "price": float(cart_item.price_at_addition),
                        "item_total": round(item_total, 2),
                    }
                )

            cart.is_active = False
            cart.save()

            return Response(
                {
                    "success": True,
                    "message": "Purchase completed successfully",
                    "purchased_items": purchased_items,
                    "purchase_total": round(purchase_total, 2),
                    "item_count": len(purchased_items),
                },
                status=status.HTTP_200_OK,
            )

    except Exception as e:
        return Response(
            {"success": False, "error": "Purchase failed", "detail": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@transaction.atomic
def confirm_purchase_with_changes(request):
    if "user_id" not in request.data:
        return Response(
            {"success": False, "error": "user_id is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user_id = request.data["user_id"]

    try:
        cart = Cart.objects.get(user_id=user_id, is_active=True)
    except Cart.DoesNotExist:
        return Response(
            {"success": False, "error": "No active cart found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    try:
        with transaction.atomic():
            purchased_items = []
            warnings = []
            purchase_total = 0.0

            for cart_item in cart.items.all():
                item = cart_item.item
                price_changed = item.price != cart_item.price_at_addition

                if item.quantity < cart_item.quantity:
                    if item.quantity > 0:
                        warnings.append(
                            {
                                "item_id": item.id,
                                "name": item.name,
                                "type": "quantity_adjusted",
                                "requested": cart_item.quantity,
                                "adjusted_to": item.quantity,
                            }
                        )
                        cart_item.quantity = item.quantity
                        cart_item.save()
                    else:
                        warnings.append(
                            {
                                "item_id": item.id,
                                "name": item.name,
                                "type": "item_removed",
                                "reason": "out_of_stock",
                            }
                        )
                        cart_item.delete()
                        continue

                item.quantity -= cart_item.quantity
                item.save()

                item_total = float(item.price) * cart_item.quantity
                purchase_total += item_total

                PurchaseLog.objects.create(
                    user_id=user_id,
                    item=item,
                    quantity=cart_item.quantity,
                    purchase_price=item.price,
                )

                purchased_items.append(
                    {
                        "item_id": item.id,
                        "name": item.name,
                        "quantity": cart_item.quantity,
                        "price": float(item.price),
                        "price_changed": price_changed,
                        "item_total": round(item_total, 2),
                    }
                )

            cart.is_active = False
            cart.save()

            response_data = {
                "success": True,
                "message": "Purchase completed with adjustments",
                "purchased_items": purchased_items,
                "purchase_total": round(purchase_total, 2),
                "item_count": len(purchased_items),
            }

            if warnings:
                response_data["warnings"] = warnings

            return Response(response_data, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {
                "success": False,
                "error": "Purchase confirmation failed",
                "detail": str(e),
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["DELETE"])
@transaction.atomic
def remove_from_cart(request):
    required_fields = ["user_id", "item_id"]
    if not all(field in request.data for field in required_fields):
        return Response(
            {
                "success": False,
                "error": "Missing required fields",
                "required": required_fields,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        user_id = request.data["user_id"]
        item_id = request.data["item_id"]

        cart = Cart.objects.get(user_id=user_id, is_active=True)
        cart_item = CartItem.objects.get(cart=cart, item_id=item_id)
        cart_item.delete()

        return Response(
            {"success": True, "message": "Item removed from cart"},
            status=status.HTTP_200_OK,
        )

    except Cart.DoesNotExist:
        return Response(
            {"success": False, "error": "No active cart found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except CartItem.DoesNotExist:
        return Response(
            {"success": False, "error": "Item not found in cart"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {
                "success": False,
                "error": "Failed to remove item from cart",
                "detail": str(e),
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
