# Generated by Django 3.2.10 on 2022-07-01 17:40

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ackrep_web", "0003_auto_20220701_1735"),
    ]

    operations = [
        migrations.AlterField(
            model_name="item",
            name="description",
            field=models.TextField(default="", null=True),
        ),
        migrations.AlterField(
            model_name="item",
            name="label",
            field=models.TextField(default="", null=True),
        ),
    ]
