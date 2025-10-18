# Generated migration to fix field issues

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0008_superadmin_model'),
    ]

    operations = [
        # Add the groups and user_permissions fields to SuperAdmin model
        migrations.AddField(
            model_name='superadmin',
            name='groups',
            field=models.ManyToManyField(
                blank=True,
                help_text='The groups this user belongs to. A user will get all permissions granted to each of their groups.',
                related_name='superadmin_set',
                related_query_name='superadmin',
                to='auth.Group',
                verbose_name='groups'
            ),
        ),
        migrations.AddField(
            model_name='superadmin',
            name='user_permissions',
            field=models.ManyToManyField(
                blank=True,
                help_text='Specific permissions for this user.',
                related_name='superadmin_set',
                related_query_name='superadmin',
                to='auth.Permission',
                verbose_name='user permissions'
            ),
        ),
        # Add the groups and user_permissions fields to User model
        migrations.AddField(
            model_name='user',
            name='groups',
            field=models.ManyToManyField(
                blank=True,
                help_text='The groups this user belongs to. A user will get all permissions granted to each of their groups.',
                related_name='user_set',
                related_query_name='user',
                to='auth.Group',
                verbose_name='groups'
            ),
        ),
        migrations.AddField(
            model_name='user',
            name='user_permissions',
            field=models.ManyToManyField(
                blank=True,
                help_text='Specific permissions for this user.',
                related_name='user_set',
                related_query_name='user',
                to='auth.Permission',
                verbose_name='user permissions'
            ),
        ),
        # Set the db_table for User model
        migrations.AlterModelOptions(
            name='user',
            options={'db_table': 'accounts_user', 'verbose_name': 'User', 'verbose_name_plural': 'Users'},
        ),
    ]
