from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_emailverification'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='topic',
            constraint=models.UniqueConstraint(
                fields=['email'],
                condition=models.Q(email_verified=True),
                name='unique_verified_email',
            ),
        ),
    ]