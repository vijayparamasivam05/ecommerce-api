from django.urls import path
from . import views
from rest_framework.urlpatterns import format_suffix_patterns

urlpatterns = [
    path("items/", views.ItemList.as_view(), name="item-list"),
    path("add-to-cart/", views.add_to_cart, name="add-to-cart"),
    path("purchase/", views.purchase_cart, name="purchase-cart"),
]

urlpatterns = format_suffix_patterns(urlpatterns)
