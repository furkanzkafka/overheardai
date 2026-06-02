from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0007_unique_verified_email'),
    ]

    operations = [
        migrations.DeleteModel(name='NotificationSettings'),
    ]