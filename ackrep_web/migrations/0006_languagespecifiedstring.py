# Generated by Django 3.2.10 on 2022-07-14 22:56

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ackrep_web", "0005_rename_item_entity"),
    ]

    operations = [
        migrations.CreateModel(
            name="LanguageSpecifiedString",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("langtag", models.CharField(default="", max_length=8)),
                ("content", models.TextField(null=True)),
            ],
            options={
                "abstract": False,
            },
        ),
    ]
