from django.db import models
from auth_app.models import User

# Create your models here.


class Senior(models.Model):
    address = models.CharField(max_length=255)
    name = models.CharField(max_length=100)
    age = models.IntegerField()
    gender = models.CharField(max_length=10)
    phone_number = models.CharField(max_length=15)
    has_alzheimers = models.BooleanField(default=False, null=True)
    has_parkinsons = models.BooleanField(default=False, null=True)
    date = models.DateTimeField(auto_now=True)
    user_id = models.ForeignKey(User, on_delete=models.CASCADE, db_column="user_id")

    def __str__(self):
        return self.name

    class Meta:
        db_table = "senior"


class Care(models.Model):
    care_type = models.CharField(max_length=100)
    datetime = models.DateTimeField(auto_now=True)
    title = models.CharField(max_length=200, blank=True, null=True)
    content = models.TextField(blank=True, null=True)
    user_id = models.ForeignKey(User, on_delete=models.CASCADE, db_column="user_id")
    seniors = models.ManyToManyField("Senior", related_name="cares_seniors")

    def __str__(self):
        return self.care_type

    class Meta:
        db_table = "care"
