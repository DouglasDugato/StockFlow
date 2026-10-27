
from django.urls import path

from . import views

app_name = "inventory"

urlpatterns = [
    path(
        "movimentacoes/nova/",
        views.StockMovementCreateView.as_view(),
        name="movement_create",
    ),
    path(
        "movimentacoes/",
        views.StockMovementListView.as_view(),
        name="movement_history",
    ),

    path(
    "produtos/novo/",
    views.ProductCreateView.as_view(),
    name="product_create",
    ),

    path(
        "produtos/",
        views.ProductListView.as_view(),
        name="product_list",
    ),
    path(
        "categorias/nova/",
        views.CategoryCreateView.as_view(),
        name="category_create",
    ),



]


