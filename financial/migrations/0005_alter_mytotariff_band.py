

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0003_alter_distributiontransformer_unique_together'),
        ('financial', '0004_moinvoice_nbetinvoice_mytotariff_salarypayment'),
    ]

    operations = [
        migrations.AlterField(
            model_name='mytotariff',
            name='band',
            field=models.ForeignKey(help_text='Service band (A-E)', on_delete=django.db.models.deletion.CASCADE, to='common.band'),
        ),
    ]
