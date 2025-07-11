from django.urls import path
from . import views

urlpatterns = [
    path("items/", views.item_list, name="item-list"),
    path("add-to-cart/", views.add_to_cart, name="add-to-cart"),
    path("remove-from-cart/", views.remove_from_cart, name="remove-from-cart"),
    path("cart/<str:user_id>/", views.view_cart, name="view-cart"),
    path("purchase/", views.purchase_cart, name="purchase-cart"),
    path(
        "confirm-purchase/",
        views.confirm_purchase_with_changes,
        name="confirm-purchase",
    ),
]
