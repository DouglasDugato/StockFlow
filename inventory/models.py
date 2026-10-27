from django.db import models, transaction
from django.conf import settings
from django.core.exceptions import ValidationError



class Category(models.Model):
    name = models.CharField(max_length=25, blank=True, null=True)
    owner = models.ForeignKey(
    settings.AUTH_USER_MODEL,
    on_delete=models.CASCADE,
    related_name='categories',
)

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=150)                 
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="products",
    )
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock_quantity = models.PositiveIntegerField(default=0)
    minimum_stock = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='products')

    def __str__(self):
        return self.name



class StockMovement(models.Model):

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="stock_movement_quantity_gt_zero",
            ),
        ]

    class MovementType(models.TextChoices):
        ENTRY = "ENTRADA", "Entrada"
        SALE = "VENDA", "Venda"


    applied = models.BooleanField(default=False)

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="stock_movements"
    )

    movement_type = models.CharField(
        max_length=20,
        choices=MovementType.choices
    )

    quantity = models.PositiveIntegerField()

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="stock_movements",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.product} - {self.movement_type} - {self.quantity}"

    def apply(self):
        
        with transaction.atomic():

            movement = StockMovement.objects.select_for_update().get(pk=self.pk)



            if movement.applied:
                raise ValidationError('mudar texto')

            if movement.quantity <= 0:
                raise ValidationError('Quantidade deve ser maior que 0')

            product = Product.objects.select_for_update().get(pk=movement.product_id) #type: ignore

            if product.owner != movement.user:
                raise ValidationError("Você não pode movimentar o estoque de outro usuário.")


            if movement.movement_type == StockMovement.MovementType.ENTRY:

                product.stock_quantity += movement.quantity

            elif movement.movement_type == StockMovement.MovementType.SALE:
                if product.stock_quantity < movement.quantity:
                    raise ValidationError('Quantidade em estoque insuficiente')
                else:
                    product.stock_quantity -= movement.quantity

            else:
                raise ValidationError('Tipo de movimentação é invalida')

            
            movement.applied = True

            product.save()
            movement.save()