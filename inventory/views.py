from typing import Any

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import redirect, render
from django.views import View
from django.views.generic.base import TemplateView
from django.views.generic import ListView
from .forms import StockMovementForm, ProductForm, CategoryForm
from .models import StockMovement, Product, Category


class StockMovementCreateView(LoginRequiredMixin, View):
    template_name = "inventory/movement_form.html"

    def get(self, request):
        form = StockMovementForm(user=request.user)
        return render(
            request,
            self.template_name,
            {"form": form},
        )

    def post(self, request):
        form = StockMovementForm(user=request.user, data=request.POST)

        if form.is_valid():
            try:
                with transaction.atomic():
                    movement = form.save(commit=False)
                    movement.user = request.user
                    movement.save()
                    movement.apply()

                messages.success(
                    request,
                    "Movimentação registrada com sucesso!",
                )
                return redirect("inventory:movement_create")

            except ValidationError as error:
                form.add_error(None, error)

        return render(
            request,
            self.template_name,
            {"form": form},
        )


class StockMovementListView(LoginRequiredMixin, TemplateView):
    template_name = 'inventory/stockhistory.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["movements"] = StockMovement.objects.filter(user=self.request.user).order_by('-created_at')

        return context

class ProductCreateView(LoginRequiredMixin, View):
    template_name = 'inventory/product_form.html'

    def get(self, request):
        form = ProductForm(user = request.user)
        return render(
            request,
            self.template_name,
            {"form": form}
        )

    def post(self, request):
        form = ProductForm(user=request.user, data=request.POST)

        if form.is_valid():
            product = form.save(commit=False)
            product.owner = request.user
            product.save()

            messages.success(request, "Produto cadastrado com sucesso!")
            return redirect("inventory:product_create")

        return render(
            request,
            self.template_name,
            {"form": form},
        )

    
class ProductListView(LoginRequiredMixin, ListView):
    model = Product
    template_name = "inventory/product_list.html"
    context_object_name = "products"

    def get_queryset(self):
        meus_produtos =  Product.objects.filter(owner=self.request.user)

        search = self.request.GET.get("q", "")

        if search:
            meus_produtos = meus_produtos.filter(name__icontains=search)

        return meus_produtos

class CategoryCreateView(LoginRequiredMixin, View):
    model = Category
    template_name = "inventory/category_form.html"

    def get(self, request):
        form = CategoryForm()

        return render(
            request,
            self.template_name,
            {"form": form}
        )

    def post(self, request):
        form = CategoryForm(data=request.POST )

        if form.is_valid():
            category = form.save(commit=False)
            category.owner = request.user
            category.save()

            messages.success(request, "Categoria cadastrada com sucesso!")
            return redirect("inventory:product_create")

        return render(
            request,
            self.template_name,
            {"form": form},
        )
