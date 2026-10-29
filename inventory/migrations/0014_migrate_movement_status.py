from django.db import migrations


def migrate_status(apps, schema_editor):
    StockMovement = apps.get_model("inventory", "StockMovement")

    StockMovement.objects.filter(applied=True).update(
        status="APLICADA"
    )

    StockMovement.objects.filter(applied=False).update(
        status="PENDENTE"
    )


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0013_stockmovement_status"),
    ]

    operations = [
        migrations.RunPython(migrate_status, migrations.RunPython.noop),
    ]