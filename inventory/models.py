from django.db import models
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from decimal import Decimal


class Item(models.Model):
    name = models.CharField(max_length=255)
    price = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    quantity = models.IntegerField(validators=[MinValueValidator(0)])

    def clean(self):
        if self.quantity < 0:
            raise ValidationError("Quantity cannot be negative")
        if self.price <= Decimal("0.00"):
            raise ValidationError("Price must be positive")

        if abs(self.price.as_tuple().exponent) != 2:
            self.price = round(self.price, 2)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Cart(models.Model):
    user_id = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def clean(self):
        if not self.user_id:
            raise ValidationError("User ID is required")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Cart {self.id} for user {self.user_id}"


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, related_name="items", on_delete=models.CASCADE)
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    quantity = models.IntegerField(validators=[MinValueValidator(1)])
    price_at_addition = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )

    def clean(self):
        if self.quantity > self.item.quantity:
            raise ValidationError(
                f"Requested quantity ({self.quantity}) exceeds available stock ({self.item.quantity})"
            )
        if self.price_at_addition <= Decimal("0.00"):
            raise ValidationError("Price at addition must be positive")

        if abs(self.price_at_addition.as_tuple().exponent) != 2:
            self.price_at_addition = round(self.price_at_addition, 2)

    def save(self, *args, **kwargs):
        self.full_clean()
        if not self.price_at_addition:
            self.price_at_addition = Decimal(self.item.price).quantize(Decimal("0.01"))
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.quantity} x {self.item.name} in cart {self.cart.id}"


class PurchaseLog(models.Model):
    user_id = models.CharField(max_length=255)
    item = models.ForeignKey(Item, on_delete=models.SET_NULL, null=True)
    quantity = models.IntegerField(validators=[MinValueValidator(1)])
    purchase_price = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    purchased_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        if self.quantity <= 0:
            raise ValidationError("Purchase quantity must be positive")
        if self.purchase_price <= Decimal("0.00"):
            raise ValidationError("Purchase price must be positive")

        if abs(self.purchase_price.as_tuple().exponent) != 2:
            self.purchase_price = round(self.purchase_price, 2)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user_id} purchased {self.quantity} x {self.item.name if self.item else 'deleted-item'} at {self.purchase_price}"
