from django.test import TestCase
from django.contrib.auth import get_user_model
from inventory.models import Category, Product, StockMovement
from django.core.exceptions import ValidationError
from unittest.mock import patch
from django.db import IntegrityError, transaction
from django.test import TransactionTestCase
from django.db import close_old_connections
from threading import Barrier
from concurrent.futures import ThreadPoolExecutor
from inventory.forms import ProductForm ,StockMovementForm, CategoryForm


class StockMovementTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="tester",
            password="test123"
        )

        self.category = Category.objects.create(
        name="Teste",
        owner=self.user,)

        self.product = Product.objects.create(
            name="Produto teste",
            category=self.category,
            price=10,
            stock_quantity=10,
            minimum_stock=2,
            owner=self.user
        )


class StockMovementConcurrencyTest(TransactionTestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
        username="concurrent_tester",
        password="test123"
    )

        self.category = Category.objects.create(
        name="Concorrência",
        owner=self.user,
    )

        self.product = Product.objects.create(
        name="Produto concorrente",
        category=self.category,
        price=10,
        stock_quantity=10,
        minimum_stock=2,
        owner=self.user,
    )

    def test_entry_increases_stock(self):
        movement = StockMovement.objects.create(
            product=self.product,
            movement_type=StockMovement.MovementType.ENTRY,
            quantity=5,
            user=self.user,
        )

        movement.apply()

        self.product.refresh_from_db()  

        self.assertEqual(self.product.stock_quantity, 15)


    def test_cancel_entry_reverts_stock(self):
        movement = StockMovement.objects.create(
        product=self.product,
        movement_type=StockMovement.MovementType.ENTRY,
        quantity=5,
        user=self.user,
    )

        movement.apply()

        movement.cancel()


        self.product.refresh_from_db()
        movement.refresh_from_db()

        self.assertEqual(self.product.stock_quantity, 10)
        self.assertEqual(movement.status, StockMovement.Status.CANCELLED)

    def test_cancel_sale_reverts_stock(self):
        movement = StockMovement.objects.create(
            product=self.product,
            movement_type=StockMovement.MovementType.SALE,
            quantity=4,
            user=self.user,
        )

        movement.apply()
        movement.cancel()

        self.product.refresh_from_db()
        movement.refresh_from_db()

        self.assertEqual(self.product.stock_quantity, 10)
        self.assertEqual(movement.status, StockMovement.Status.CANCELLED)


    def test_cannot_cancel_pending_movement(self):
        movement = StockMovement.objects.create(
            product=self.product,
            movement_type=StockMovement.MovementType.SALE,
            quantity=4,
            user=self.user,
        )
        with self.assertRaises(ValidationError):
            movement.cancel()

        self.product.refresh_from_db()
        movement.refresh_from_db()

        self.assertEqual(self.product.stock_quantity, 10)
        self.assertEqual(movement.status, StockMovement.Status.PENDING)


    def test_cannot_cancel_movement_twice(self):
        movement = StockMovement.objects.create(
        product=self.product,
        movement_type=StockMovement.MovementType.ENTRY,
        quantity=5,
        user=self.user,
        )

        movement.apply()
        movement.cancel()

        self.product.refresh_from_db()
        movement.refresh_from_db()

        with self.assertRaises(ValidationError):
            movement.cancel()

        self.assertEqual(self.product.stock_quantity, 10)
        self.assertEqual(movement.status, StockMovement.Status.CANCELLED)


    def test_cannot_cancel_entry_if_stock_is_insufficient(self):
        movement = StockMovement.objects.create(
        product=self.product,
        movement_type=StockMovement.MovementType.ENTRY,
        quantity=5,
        user=self.user)

        movement.apply()


        self.product.refresh_from_db()
        movement.refresh_from_db()

        self.assertEqual(self.product.stock_quantity, 15)
        self.assertEqual(movement.status, StockMovement.Status.APPLIED)

        movement = StockMovement.objects.create(
        product=self.product,
        movement_type=StockMovement.MovementType.SALE,
        quantity=12,
        user=self.user)

        movement.apply()

        self.product.refresh_from_db()
        movement.refresh_from_db()


        self.assertEqual(self.product.stock_quantity, 3)
        self.assertEqual(movement.status, StockMovement.Status.APPLIED)

        movement = StockMovement.objects.get(
        product=self.product,
        movement_type=StockMovement.MovementType.ENTRY,
        quantity=5,
        user=self.user)

        with self.assertRaises(ValidationError):
            movement.cancel()

        self.product.refresh_from_db()
        movement.refresh_from_db()


        self.assertEqual(self.product.stock_quantity, 3)
        self.assertEqual(movement.status, StockMovement.Status.APPLIED)

    def test_sale_stock(self):
        movement = StockMovement.objects.create(
            product=self.product,
            movement_type=StockMovement.MovementType.SALE,
            quantity=3,
            user=self.user,
        )

        movement.apply()

        self.product.refresh_from_db()

        self.assertEqual(self.product.stock_quantity, 7)

    def test_sale_decrease_failure(self):
        movement = StockMovement.objects.create(
            product=self.product,
            movement_type=StockMovement.MovementType.SALE,
            quantity=15,
            user=self.user,
        )

        with self.assertRaises(ValidationError):
            movement.apply()

        self.product.refresh_from_db()

        self.assertEqual(self.product.stock_quantity, 10)

    def test_movement_cannot_be_applied_twice(self):
        movement = StockMovement.objects.create(
            product=self.product,
            movement_type=StockMovement.MovementType.ENTRY,
            quantity=5,
            user=self.user,
        )

        movement.apply()

        with self.assertRaises(ValidationError):
            movement.apply()

        self.product.refresh_from_db()

        self.assertEqual(self.product.stock_quantity, 15)


    def test_movement_rejects_zero_quantity(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                StockMovement.objects.create(
                    product=self.product,
                    movement_type=StockMovement.MovementType.ENTRY,
                    quantity=0,
                    user=self.user,
                )

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 10)


    def test_movement_rejects_negative_quantity(self):
        movement = StockMovement(
        product=self.product,
        movement_type=StockMovement.MovementType.ENTRY,
        quantity=-5,
        user=self.user,
    )

        with self.assertRaises(ValidationError):
         movement.full_clean()


    def test_movement_rolls_back_if_saving_movement_fails(self):
        movement = StockMovement.objects.create(
            product=self.product,
            movement_type=StockMovement.MovementType.ENTRY,
            quantity=5,
            user=self.user,
        )

        with patch.object(
            StockMovement,
            "save",
            side_effect=RuntimeError("Falha simulada"),
        ):
            with self.assertRaises(RuntimeError):
                movement.apply()

        self.product.refresh_from_db()
        movement.refresh_from_db()

        self.assertEqual(self.product.stock_quantity, 10)
        self.assertEqual(movement.status, StockMovement.Status.PENDING)


    def test_product_cannot_use_another_users_category(self):
        another_user = get_user_model().objects.create_user(
            username="another_user",
            password="test123"
        )

        another_category = Category.objects.create(
            name="Categoria alheia",
            owner=another_user,
        )

        with self.assertRaises(ValidationError):
            Product.objects.create(
                name="Produto de teste",
                category=another_category,
                price=10,
                owner=self.user,
            )


    
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse

from inventory.models import Category, Product, StockMovement


class InventoryViewsSecurityTest(TestCase):

    def setUp(self):
        User = get_user_model()

        self.user1 = User.objects.create_user(
            username="usuario1",
            password="senha123"
        )

        self.user2 = User.objects.create_user(
            username="usuario2",
            password="senha123"
        )

        self.client1 = Client()
        self.client2 = Client()

        self.category1 = Category.objects.create(
            name="Categoria 1",
            owner=self.user1
        )

        self.category2 = Category.objects.create(
            name="Categoria 2",
            owner=self.user2
        )

        self.product1 = Product.objects.create(
            name="Produto 1",
            category=self.category1,
            price=10,
            stock_quantity=10,
            owner=self.user1
        )

        self.product2 = Product.objects.create(
            name="Produto 2",
            category=self.category2,
            price=20,
            stock_quantity=20,
            owner=self.user2
        )

    def test_anonymous_user_cannot_access_product_list(self):
        response = self.client1.get(
            reverse("inventory:product_list")
        )

        self.assertEqual(response.status_code, 302)

    def test_anonymous_user_cannot_access_dashboard(self):
        response = self.client1.get(
            reverse("users:dashboard")
        )

        self.assertEqual(response.status_code, 302)

    def test_user_queryset_contains_only_own_products(self):
        self.client1.login(
            username="usuario1",
            password="senha123"
        )

        response = self.client1.get(
            reverse("inventory:product_list")
        )

        self.assertEqual(response.status_code, 200)

        self.assertQuerySetEqual(
            response.context["products"].order_by("id"),
            [self.product1]
        )

    def test_user_sees_only_own_categories_in_product_form(self):
        self.client1.login(
            username="usuario1",
            password="senha123"
        )

        response = self.client1.get(
            reverse("inventory:product_create")
        )

        self.assertEqual(response.status_code, 200)

        category_queryset = response.context["form"].fields["category"].queryset

        self.assertQuerySetEqual(
            category_queryset.order_by("id"),
            [self.category1]
        )

    def test_user_cannot_create_product_with_another_users_category(self):
        self.client1.login(
            username="usuario1",
            password="senha123"
        )

        response = self.client1.post(
            reverse("inventory:product_create"),
            {
                "name": "Produto inválido",
                "category": self.category2.pk,
                "price": "10.00",
                "minimum_stock": 1,
            }
        )

        self.assertEqual(response.status_code, 200)

        self.assertFalse(
            Product.objects.filter(name="Produto inválido").exists()
        )

    def test_user_sees_only_own_movements(self):
        StockMovement.objects.create(
            product=self.product1,
            movement_type=StockMovement.MovementType.ENTRY,
            quantity=5,
            user=self.user1,
        )

        StockMovement.objects.create(
            product=self.product2,
            movement_type=StockMovement.MovementType.ENTRY,
            quantity=5,
            user=self.user2,
        )

        self.client1.login(
            username="usuario1",
            password="senha123"
        )

        response = self.client1.get(
            reverse("inventory:movement_history")
        )

        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            list(response.context["movements"].values_list("user_id", flat=True)),
            [self.user1.pk]
        )

    def test_user_cannot_cancel_another_users_movement(self):
        movement = StockMovement.objects.create(
            product=self.product2,
            movement_type=StockMovement.MovementType.ENTRY,
            quantity=5,
            user=self.user2,
        )

        self.client1.login(
            username="usuario1",
            password="senha123"
        )

        response = self.client1.post(
            reverse(
                "inventory:movement_cancel",
                kwargs={"pk": movement.pk}
            )
        )

        self.assertEqual(response.status_code, 404)

        movement.refresh_from_db()

        self.assertEqual(
            movement.status,
            StockMovement.Status.PENDING
        )

        self.product2.refresh_from_db()

        self.assertEqual(self.product2.stock_quantity, 20)



from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse


class AuthenticationAndProfileTest(TestCase):

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="perfil_teste",
            password="senha123",
            first_name="Douglas",
            last_name="Teste",
        )

        self.client = Client()

    def test_login_with_correct_credentials(self):
        response = self.client.post(
            reverse("users:login"),
            {
                "username": "perfil_teste",
                "password": "senha123",
            }
        )

        self.assertRedirects(
            response,
            reverse("users:dashboard")
        )

        self.assertTrue(
            self.client.session.get("_auth_user_id")
        )

    def test_login_with_wrong_password(self):
        response = self.client.post(
            reverse("users:login"),
            {
                "username": "perfil_teste",
                "password": "senha_errada",
            }
        )

        self.assertEqual(response.status_code, 200)

        self.assertFalse(
            self.client.session.get("_auth_user_id")
        )

    def test_authenticated_user_is_redirected_from_login(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("users:login")
        )

        self.assertRedirects(
            response,
            reverse("users:dashboard")
        )

    def test_anonymous_user_cannot_access_profile(self):
        response = self.client.get(
            reverse("users:profile")
        )

        self.assertEqual(response.status_code, 302)

    def test_user_can_update_first_and_last_name(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("users:profile"),
            {
                "form_type": "profile",
                "first_name": "Douglas Novo",
                "last_name": "Dugato",
            }
        )

        self.assertEqual(response.status_code, 200)

        self.user.refresh_from_db()

        self.assertEqual(self.user.first_name, "Douglas Novo")
        self.assertEqual(self.user.last_name, "Dugato")

    def test_user_can_change_password(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("users:profile"),
            {
                "form_type": "password",
                "old_password": "senha123",
                "new_password1": "NovaSenha123!abc",
                "new_password2": "NovaSenha123!abc",
            }
        )

        self.assertEqual(response.status_code, 200)

        self.user.refresh_from_db()

        self.assertTrue(
            self.user.check_password("NovaSenha123!abc")
        )

    def test_session_remains_active_after_password_change(self):
        self.client.force_login(self.user)

        self.client.post(
            reverse("users:profile"),
            {
                "form_type": "password",
                "old_password": "senha123",
                "new_password1": "NovaSenha123!abc",
                "new_password2": "NovaSenha123!abc",
            }
        )

        response = self.client.get(
            reverse("users:profile")
        )

        self.assertEqual(response.status_code, 200)

    def test_user_cannot_change_password_with_wrong_old_password(self):
        self.client.force_login(self.user)

        self.client.post(
            reverse("users:profile"),
            {
                "form_type": "password",
                "old_password": "senha_errada",
                "new_password1": "NovaSenha123!abc",
                "new_password2": "NovaSenha123!abc",
            }
        )

        self.user.refresh_from_db()

        self.assertTrue(
            self.user.check_password("senha123")
        )


class InventoryFormsTest(TestCase):

    def setUp(self):
        User = get_user_model()

        self.user1 = User.objects.create_user(
            username="forms_user1",
            password="senha123",
        )

        self.user2 = User.objects.create_user(
            username="forms_user2",
            password="senha123",
        )

        self.category1 = Category.objects.create(
            name="Categoria 1",
            owner=self.user1,
        )

        self.category2 = Category.objects.create(
            name="Categoria 2",
            owner=self.user2,
        )

        self.product1 = Product.objects.create(
            name="Produto 1",
            category=self.category1,
            price=25.00,
            stock_quantity=10,
            owner=self.user1,
        )

        self.product2 = Product.objects.create(
            name="Produto 2",
            category=self.category2,
            price=30.00,
            stock_quantity=10,
            owner=self.user2,
        )

    def test_product_form_accepts_valid_data(self):
        form = ProductForm(
            user=self.user1,
            data={
                "name": "Novo Produto",
                "category": self.category1.pk,
                "price": "50.00",
                "minimum_stock": 2,
            },
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_product_form_rejects_category_from_another_user(self):
        form = ProductForm(
            user=self.user1,
            data={
                "name": "Produto Inválido",
                "category": self.category2.pk,
                "price": "50.00",
                "minimum_stock": 2,
            },
        )

        self.assertFalse(form.is_valid())
        self.assertIn("category", form.errors)

    def test_product_form_rejects_missing_name(self):
        form = ProductForm(
            user=self.user1,
            data={
                "name": "",
                "category": self.category1.pk,
                "price": "50.00",
                "minimum_stock": 2,
            },
        )

        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors)

    def test_stock_movement_form_accepts_valid_data(self):
        form = StockMovementForm(
            user=self.user1,
            data={
                "product": self.product1.pk,
                "movement_type": StockMovement.MovementType.SALE,
                "quantity": 2,
            },
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_stock_movement_form_rejects_another_users_product(self):
        form = StockMovementForm(
            user=self.user1,
            data={
                "product": self.product2.pk,
                "movement_type": StockMovement.MovementType.SALE,
                "quantity": 2,
            },
        )

        self.assertFalse(form.is_valid())
        self.assertIn("product", form.errors)

    def test_stock_movement_form_rejects_zero_quantity(self):
        form = StockMovementForm(
            user=self.user1,
            data={
                "product": self.product1.pk,
                "movement_type": StockMovement.MovementType.SALE,
                "quantity": 0,
            },
        )

        

        self.assertFalse(form.is_valid())
        self.assertIn("quantity", form.errors)

        self.assertFalse(form.is_valid())
        self.assertIn("quantity", form.errors)

    def test_category_form_accepts_valid_data(self):
        form = CategoryForm(
            data={"name": "Nova Categoria"}
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_category_form_accepts_empty_name(self):
        form = CategoryForm(
            data={"name": ""}
        )

        self.assertTrue(form.is_valid(), form.errors)



class InventoryViewsTest(TestCase):

    def setUp(self):
        User = get_user_model()

        self.user = User.objects.create_user(
            username="views_user",
            password="senha123",
        )

        self.other_user = User.objects.create_user(
            username="views_other",
            password="senha123",
        )

        self.client.force_login(self.user)

        self.category = Category.objects.create(
            name="Suplementos",
            owner=self.user,
        )

        self.other_category = Category.objects.create(
            name="Outra categoria",
            owner=self.other_user,
        )

        self.product = Product.objects.create(
            name="Produto Teste",
            category=self.category,
            price=50.00,
            stock_quantity=10,
            minimum_stock=2,
            owner=self.user,
        )

    def test_category_creation_assigns_logged_user_as_owner(self):
        response = self.client.post(
            reverse("inventory:category_create"),
            {"name": "Bebidas"},
        )

        self.assertRedirects(
            response,
            reverse("inventory:product_create"),
        )

        category = Category.objects.get(name="Bebidas")

        self.assertEqual(category.owner, self.user)

    def test_product_creation_assigns_logged_user_as_owner(self):
        response = self.client.post(
            reverse("inventory:product_create"),
            {
                "name": "Novo Produto",
                "category": self.category.pk,
                "price": "75.00",
                "minimum_stock": 3,
            },
        )

        self.assertRedirects(
            response,
            reverse("inventory:product_create"),
        )

        product = Product.objects.get(name="Novo Produto")

        self.assertEqual(product.owner, self.user)
        self.assertEqual(product.stock_quantity, 0)

    def test_product_creation_rejects_invalid_data(self):
        response = self.client.post(
            reverse("inventory:product_create"),
            {
                "name": "",
                "category": self.category.pk,
                "price": "75.00",
                "minimum_stock": 3,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            Product.objects.filter(name="").exists()
        )

    def test_category_creation_rejects_invalid_data(self):
        # O campo name permite vazio no modelo atual.
        # Portanto, testamos um nome acima do limite de 25 caracteres.
        response = self.client.post(
            reverse("inventory:category_create"),
            {"name": "A" * 26},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            Category.objects.filter(name="A" * 26).exists()
        )

    def test_movement_creation_applies_entry_to_stock(self):
        response = self.client.post(
            reverse("inventory:movement_create"),
            {
                "product": self.product.pk,
                "movement_type": StockMovement.MovementType.ENTRY,
                "quantity": 5,
            },
        )

        self.assertRedirects(
            response,
            reverse("inventory:movement_create"),
        )

        self.product.refresh_from_db()

        self.assertEqual(self.product.stock_quantity, 15)

        movement = StockMovement.objects.get(
            product=self.product,
            user=self.user,
        )

        self.assertEqual(
            movement.status,
            StockMovement.Status.APPLIED,
        )

    def test_movement_creation_applies_sale_to_stock(self):
        response = self.client.post(
            reverse("inventory:movement_create"),
            {
                "product": self.product.pk,
                "movement_type": StockMovement.MovementType.SALE,
                "quantity": 3,
            },
        )

        self.assertRedirects(
            response,
            reverse("inventory:movement_create"),
        )

        self.product.refresh_from_db()

        self.assertEqual(self.product.stock_quantity, 7)

    def test_failed_sale_does_not_create_movement(self):
        movements_before = StockMovement.objects.count()

        response = self.client.post(
            reverse("inventory:movement_create"),
            {
                "product": self.product.pk,
                "movement_type": StockMovement.MovementType.SALE,
                "quantity": 50,
            },
        )

        self.assertEqual(response.status_code, 200)

        self.product.refresh_from_db()

        self.assertEqual(self.product.stock_quantity, 10)
        self.assertEqual(
            StockMovement.objects.count(),
            movements_before,
        )

    def test_cancel_view_reverses_applied_movement(self):
        movement = StockMovement.objects.create(
            product=self.product,
            movement_type=StockMovement.MovementType.SALE,
            quantity=3,
            user=self.user,
        )

        movement.apply()

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 7)

        response = self.client.post(
            reverse(
                "inventory:movement_cancel",
                kwargs={"pk": movement.pk},
            )
        )

        self.assertRedirects(
            response,
            reverse("inventory:movement_history"),
        )

        self.product.refresh_from_db()
        movement.refresh_from_db()

        self.assertEqual(self.product.stock_quantity, 10)
        self.assertEqual(
            movement.status,
            StockMovement.Status.CANCELLED,
        )

    def test_product_search_filters_by_name(self):
        Product.objects.create(
            name="Outro Suplemento",
            category=self.category,
            price=30.00,
            owner=self.user,
        )

        response = self.client.get(
            reverse("inventory:product_list"),
            {"q": "Produto Teste"},
        )

        self.assertEqual(response.status_code, 200)

        products = list(response.context["products"])

        self.assertEqual(products, [self.product])



class ProductUpdateViewTest(TestCase):

    def setUp(self):
        User = get_user_model()

        self.user = User.objects.create_user(
            username="editor",
            password="senha123"
        )

        self.other_user = User.objects.create_user(
            username="outro_usuario",
            password="senha123"
        )

        self.category = Category.objects.create(
            name="Suplementos",
            owner=self.user
        )

        self.product = Product.objects.create(
            name="Produto Original",
            category=self.category,
            price=50.00,
            stock_quantity=10,
            minimum_stock=2,
            owner=self.user
        )

        self.client.force_login(self.user)

    def test_user_can_access_product_update_page(self):
        response = self.client.get(
            reverse(
                "inventory:product_update",
                kwargs={"pk": self.product.pk}
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["form"].instance,
            self.product
        )

    def test_user_can_update_product(self):
        response = self.client.post(
            reverse(
                "inventory:product_update",
                kwargs={"pk": self.product.pk}
            ),
            {
                "name": "Produto Atualizado",
                "category": self.category.pk,
                "price": "75.00",
                "minimum_stock": 5,
            }
        )

        self.assertRedirects(
            response,
            reverse("users:dashboard")
        )

        self.product.refresh_from_db()

        self.assertEqual(self.product.name, "Produto Atualizado")
        self.assertEqual(self.product.price, 75.00)
        self.assertEqual(self.product.minimum_stock, 5)

    def test_update_does_not_create_duplicate_product(self):
        products_before = Product.objects.count()

        self.client.post(
            reverse(
                "inventory:product_update",
                kwargs={"pk": self.product.pk}
            ),
            {
                "name": "Produto Atualizado",
                "category": self.category.pk,
                "price": "75.00",
                "minimum_stock": 5,
            }
        )

        self.assertEqual(
            Product.objects.count(),
            products_before
        )

    def test_user_cannot_update_another_users_product(self):
        other_category = Category.objects.create(
            name="Outra categoria",
            owner=self.other_user
        )

        other_product = Product.objects.create(
            name="Produto Alheio",
            category=other_category,
            price=30.00,
            stock_quantity=5,
            owner=self.other_user
        )

        response = self.client.get(
            reverse(
                "inventory:product_update",
                kwargs={"pk": other_product.pk}
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_invalid_update_does_not_change_product(self):
        response = self.client.post(
            reverse(
                "inventory:product_update",
                kwargs={"pk": self.product.pk}
            ),
            {
                "name": "",
                "category": self.category.pk,
                "price": "75.00",
                "minimum_stock": 5,
            }
        )

        self.assertEqual(response.status_code, 200)

        self.product.refresh_from_db()

        self.assertEqual(self.product.name, "Produto Original")
        self.assertEqual(self.product.price, 50.00)
