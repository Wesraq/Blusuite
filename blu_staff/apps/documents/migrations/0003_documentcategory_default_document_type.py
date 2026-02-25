from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("documents", "0002_alter_employeedocument_approved_by"),
    ]

    operations = [
        migrations.AddField(
            model_name="documentcategory",
            name="default_document_type",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Optional default document type value used when uploading documents automatically.",
                max_length=20,
                verbose_name="default document type",
            ),
        ),
    ]
