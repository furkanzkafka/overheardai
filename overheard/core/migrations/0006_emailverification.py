import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_topic_email_alter_matcheditem_platform'),
    ]

    operations = [
        migrations.AddField(
            model_name='topic',
            name='email_verified',
            field=models.BooleanField(default=False),
        ),
        migrations.CreateModel(
            name='EmailVerification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('email', models.EmailField(max_length=254)),
                ('code', models.CharField(max_length=6)),
                ('attempts', models.IntegerField(default=0)),
                ('consumed', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField()),
                ('topic', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='verifications', to='core.topic')),
            ],
            options={'ordering': ['-created_at']},
        ),
    ]