import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
        ("plugin_practice", "0002_practicegoal_add_goal_fk"),
    ]

    operations = [
        migrations.AddField(
            model_name="practicegoal",
            name="category",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="practice_goals",
                to="core.category",
            ),
        ),
    ]
