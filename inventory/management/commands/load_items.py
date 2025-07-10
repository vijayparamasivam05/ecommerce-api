from django.core.management.base import BaseCommand
from inventory.models import Item
import json


class Command(BaseCommand):
    help = "Load initial items data from JSON file"

    def handle(self, *args, **options):
        with open("MOCK_DATA.json", "r") as f:
            items_data = json.load(f)

        for item_data in items_data:
            Item.objects.create(
                name=item_data["name"],
                price=item_data["price"],
                quantity=item_data["quantity"],
            )

        self.stdout.write(self.style.SUCCESS("Successfully loaded items data"))
