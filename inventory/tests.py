from django.test import TestCase
from django.contrib.auth import get_user_model
from inventory.models import Category, Product, StockMovement
from django.core.exceptions import ValidationError
from unittest.mock import patch
from django.db import IntegrityError, transaction


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
