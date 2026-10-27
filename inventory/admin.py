from django.contrib import admin
from . import models

@admin.register(models.Category)
class CategoryAdmin(admin.ModelAdmin):
    pass


@admin.register(models.Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "price", "stock_quantity")
    list_filter = ("category", "is_active")
    search_fields = ("name",)

@admin.register(models.StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    pass