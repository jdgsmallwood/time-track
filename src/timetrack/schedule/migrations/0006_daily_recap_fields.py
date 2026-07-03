from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("schedule", "0005_dailycheckin_dailygoalprogress"),
    ]

    operations = [
        migrations.AddField(
            model_name="dailycheckin",
            name="recap_wins",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="dailycheckin",
            name="recap_misses",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="dailycheckin",
            name="recap_energy_score",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="dailycheckin",
            name="recap_completed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="dailygoalprogress",
            name="actual",
            field=models.TextField(blank=True),
        ),
    ]
