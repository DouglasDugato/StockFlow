from django.shortcuts import render
from django.contrib.auth.views import LoginView
from django.urls import reverse
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from inventory.models import Product, StockMovement
from django.db.models import F
from django.shortcuts import redirect


class LoginUserView(LoginView):
    template_name = "users/_login.html"
    redirect_authenticated_user = True

    def get_success_url(self):
        return reverse('users:dashboard')


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "users/_dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        produtos_search =  Product.objects.filter(owner=self.request.user)

        search = self.request.GET.get("q", "")

        if search:
            produtos_search = produtos_search.filter(name__icontains=search)
        context['produtos_pesquisa'] = produtos_search
        context['pesquisa_search'] = search


        context["total_produtos"] = Product.objects.filter(owner=self.request.user).count()
        context['produtos_estoque_baixo'] = Product.objects.filter(stock_quantity__lte=F('minimum_stock')).filter(owner=self.request.user).count()
        context['produtos_baixo_estoque'] = Product.objects.filter(stock_quantity__lte=F('minimum_stock')).filter(owner=self.request.user)
        context["movimentos_estoques_qtd"] = StockMovement.objects.filter(user=self.request.user,applied=True).count()
        context["produtos"] = Product.objects.filter(owner=self.request.user)


        return context


    

