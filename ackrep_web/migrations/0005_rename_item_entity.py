# Generated by Django 3.2.10 on 2022-07-02 09:13

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("ackrep_web", "0004_auto_20220701_1740"),
    ]

    operations = [
        migrations.RenameModel(
            old_name="Item",
            new_name="Entity",
        ),
    ]
