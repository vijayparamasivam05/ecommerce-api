from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.decorators import api_view
from django.db import transaction
from .models import Item, Cart, CartItem, PurchaseLog
from .serializers import ItemSerializer, CartSerializer, CartItemSerializer


class ItemList(generics.ListAPIView):
    queryset = Item.objects.filter(quantity__gt=0)
    serializer_class = ItemSerializer


@api_view(["POST"])
def add_to_cart(request):
    user_id = request.data.get("user_id")
    item_id = request.data.get("item_id")
    quantity = request.data.get("quantity", 1)

    try:
        item = Item.objects.get(id=item_id)
    except Item.DoesNotExist:
        return Response({"error": "Item not found"}, status=status.HTTP_404_NOT_FOUND)

    if item.quantity < quantity:
        return Response(
            {"error": f"Not enough stock. Only {item.quantity} available"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    cart, created = Cart.objects.get_or_create(user_id=user_id, is_active=True)

    cart_item, created = CartItem.objects.get_or_create(
        cart=cart, item=item, defaults={"quantity": quantity}
    )

    if not created:
        cart_item.quantity += quantity
        cart_item.save()

    return Response({"success": "Item added to cart"}, status=status.HTTP_200_OK)


@api_view(["POST"])
@transaction.atomic
def purchase_cart(request):
    user_id = request.data.get("user_id")

    try:
        cart = Cart.objects.get(user_id=user_id, is_active=True)
    except Cart.DoesNotExist:
        return Response(
            {"error": "No active cart found"}, status=status.HTTP_404_NOT_FOUND
        )

    # Check all items have sufficient stock
    for cart_item in cart.items.all():
        if cart_item.item.quantity < cart_item.quantity:
            return Response(
                {
                    "error": f"Not enough stock for {cart_item.item.name}. Only {cart_item.item.quantity} available"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

    # Process purchase
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

    return Response({"success": "Purchase completed"}, status=status.HTTP_200_OK)
