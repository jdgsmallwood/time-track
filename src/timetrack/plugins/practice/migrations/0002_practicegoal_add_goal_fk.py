import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("plugin_practice", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="PracticeGoal",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("instrument", models.CharField(blank=True, max_length=100)),
                (
                    "focus",
                    models.CharField(
                        choices=[
                            ("technique", "Technique"),
                            ("repertoire", "Repertoire"),
                            ("sight_reading", "Sight Reading"),
                            ("theory", "Theory"),
                            ("improvisation", "Improvisation"),
                            ("band", "Band Pieces"),
                            ("free", "Free Practice"),
                        ],
                        default="free",
                        max_length=30,
                    ),
                ),
                ("duration_minutes", models.PositiveIntegerField(default=60)),
                ("recurrence_count", models.PositiveSmallIntegerField(default=1, help_text="How many times per week.")),
                ("notes", models.CharField(blank=True, max_length=200)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={"ordering": ["instrument", "focus"]},
        ),
        migrations.AddField(
            model_name="practicesession",
            name="goal",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="sessions",
                to="plugin_practice.practicegoal",
            ),
        ),
        migrations.AlterField(
            model_name="practicesession",
            name="focus",
            field=models.CharField(
                choices=[
                    ("technique", "Technique"),
                    ("repertoire", "Repertoire"),
                    ("sight_reading", "Sight Reading"),
                    ("theory", "Theory"),
                    ("improvisation", "Improvisation"),
                    ("band", "Band Pieces"),
                    ("free", "Free Practice"),
                ],
                default="free",
                max_length=30,
            ),
        ),
    ]
