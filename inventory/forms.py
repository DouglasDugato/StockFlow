from typing import Any, MutableMapping

from django import forms
from django.forms.renderers import BaseRenderer
from .models import StockMovement, Product, Category


class StockMovementForm(forms.ModelForm):
    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['product'].queryset = Product.objects.filter(owner=user) #type: ignore


    class Meta:
        model = StockMovement
        fields = ["product", "movement_type", "quantity"]
        labels = {
            "product": "Produto",
            "movement_type": "Tipo de movimentação",
            "quantity": "Quantidade",
        }
        widgets = {
            "quantity": forms.NumberInput(attrs={
                "min": 1,
                "placeholder": "Digite a quantidade",
            }),
        }


class ProductForm(forms.ModelForm):
    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["category"].queryset = Category.objects.filter(owner=user) #type: ignore



    class Meta:
        model = Product
        fields = ["name", "category", "price", "minimum_stock"]
        labels = {
            "name": "Nome do produto",
            "category": "Categoria",
            "price": "Preço",
            "minimum_stock": "Estoque mínimo",
        }


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category

        fields = ['name']