from django.db import models

class ForecastRow(models.Model):
    sku = models.CharField(max_length=50)
    week_start = models.DateField()
    forecast_units = models.FloatField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['sku', 'week_start'], name='unique_forecast_sku_week')
        ]

    def __str__(self):
        return f"{self.sku} - {self.week_start}: {self.forecast_units}"
