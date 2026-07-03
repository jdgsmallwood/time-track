from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("schedule", "0004_planweekreflection_weeklygoal"),
    ]

    operations = [
        migrations.CreateModel(
            name="DailyCheckIn",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField(unique=True)),
                ("intention", models.TextField(blank=True)),
                ("general_aims", models.TextField(blank=True)),
                ("energy_score", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name="DailyGoalProgress",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("plan", models.TextField(blank=True)),
                (
                    "check_in",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="goal_progress",
                        to="schedule.dailycheckin",
                    ),
                ),
                (
                    "goal",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="daily_progress",
                        to="schedule.weeklygoal",
                    ),
                ),
            ],
            options={
                "unique_together": {("check_in", "goal")},
            },
        ),
    ]
