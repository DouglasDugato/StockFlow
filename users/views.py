from django.shortcuts import render
from django.contrib.auth.views import LoginView
from django.urls import reverse
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from inventory.models import Product, StockMovement
from django.db.models import F
from django.shortcuts import redirect
from .forms import ProfileForm
from django.contrib import messages
from django.contrib.auth.forms import PasswordChangeForm
from typing import cast
from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth import update_session_auth_hash

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

class ProfileView(LoginRequiredMixin, TemplateView):
    template_name = "users/profile.html"



    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context.setdefault(
            "form",
            ProfileForm(instance=self.request.user))

        user = cast(AbstractBaseUser, self.request.user)
        password_form = PasswordChangeForm(user=user)
        context["password_form"] = password_form

        
        return context


    def post(self, request, *args, **kwargs):
        form_type = request.POST.get("form_type")

        if form_type == "profile":
            form = ProfileForm(
                data=request.POST,
                instance=request.user,
            )

            if form.is_valid():
                form.save()
                messages.success(request, "Dados salvos com sucesso")
                return self.render_to_response(
                    self.get_context_data(form=ProfileForm())
                )

            return self.render_to_response(
                self.get_context_data(form=form)
            )

        elif form_type == "password":
            password_form = PasswordChangeForm(
                user=request.user,
                data=request.POST,
            )

            if password_form.is_valid():
                password_form.save()
                update_session_auth_hash(request, request.user)
                messages.success(request, "Senha alterada com sucesso")
                return self.render_to_response(
                    self.get_context_data(
                        form=ProfileForm(),
                        password_form=PasswordChangeForm(
                            user=request.user
                        ),
                    )
                )

            else:
                messages.error(request,'Dados incorretos!')

            return self.render_to_response(
                self.get_context_data(password_form=password_form)
            )

        return redirect("users:profile")


